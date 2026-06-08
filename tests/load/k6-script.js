import { check, sleep, group } from "k6";
import http from "k6/http";
import { Rate, Trend, Counter } from "k6/metrics";

export const options = {
  stages: [
    { duration: "30s", target: 20 },
    { duration: "1m", target: 50 },
    { duration: "30s", target: 100 },
    { duration: "1m", target: 100 },
    { duration: "30s", target: 50 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_duration: ["p(95)<500", "p(99)<1000"],
    http_req_failed: ["rate<0.01"],
    event_ingest_duration: ["p(95)<300"],
    analytics_query_duration: ["p(95)<200"],
  },
  tags: {
    name: "analytics-pipeline",
    environment: "load-test",
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const USERNAME = __ENV.TEST_USERNAME || "loadtest";
const PASSWORD = __ENV.TEST_PASSWORD || "loadtest123!";

const eventIngestTrend = new Trend("event_ingest_duration");
const analyticsQueryTrend = new Trend("analytics_query_duration");
const dashboardTrend = new Trend("dashboard_operation_duration");
const errorRate = new Rate("error_rate");
const eventsIngested = new Counter("events_ingested");

let authToken = null;
let dashboardIds = [];

export function setup() {
  const registerPayload = JSON.stringify({
    username: USERNAME,
    email: `${USERNAME}@loadtest.example.com`,
    password: PASSWORD,
  });
  const registerRes = http.post(
    `${BASE_URL}/api/v1/auth/register`,
    registerPayload,
    { headers: { "Content-Type": "application/json" }, tags: { name: "register" } }
  );

  let token = null;
  if (registerRes.status === 201) {
    token = registerRes.json("access_token");
  }

  if (!token) {
    const loginRes = http.post(
      `${BASE_URL}/api/v1/auth/login`,
      JSON.stringify({ username: USERNAME, password: PASSWORD }),
      { headers: { "Content-Type": "application/json" }, tags: { name: "login" } }
    );
    check(loginRes, { "login successful": (r) => r.status === 200 });
    token = loginRes.json("access_token");
  }

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const dashRes = http.post(
    `${BASE_URL}/api/v1/dashboards`,
    JSON.stringify({
      name: "Load Test Dashboard",
      description: "Auto-created during load test",
      widgets: [
        {
          title: "Real-time Events",
          widget_type: "counter",
          metric_name: "events.total",
          config: {},
          position: 0,
          width: 3,
          height: 2,
        },
      ],
    }),
    { headers, tags: { name: "create_dashboard" } }
  );

  const dashIds = [];
  if (dashRes.status === 201) {
    dashIds.push(dashRes.json("dashboard_id"));
  }

  const healthRes = http.get(`${BASE_URL}/health`, {
    tags: { name: "health_setup" },
  });
  check(healthRes, { "health check ok": (r) => r.status === 200 });

  return { token, dashboardIds: dashIds };
}

export default function (data) {
  const token = data.token;
  const dashIds = data.dashboardIds;

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  group("Health Check", function () {
    const res = http.get(`${BASE_URL}/health`, {
      tags: { name: "health_check" },
    });
    check(res, {
      "health status is ok": (r) => r.json("status") === "ok",
      "health response time < 200ms": (r) => r.timings.duration < 200,
    });
  });

  group("Event Ingestion", function () {
    const events = [];
    const batchSize = Math.floor(Math.random() * 10) + 1;

    for (let i = 0; i < batchSize; i++) {
      events.push({
        event_type: randomChoice([
          "page_view", "click", "signup", "purchase",
          "login", "logout", "error", "custom",
        ]),
        source: randomChoice([
          "web-app", "mobile-app", "api-gateway",
          "admin-panel", "landing-page",
        ]),
        payload: generatePayload(),
        session_id: `loadtest-session-${__VU}`,
      });
    }

    const res = http.post(
      `${BASE_URL}/api/v1/events/ingest/batch`,
      JSON.stringify(events),
      { headers, tags: { name: "ingest_events" } }
    );

    eventIngestTrend.add(res.timings.duration);
    eventsIngested.add(events.length);

    check(res, {
      "event ingestion successful": (r) => r.status === 201,
      "all events accepted": (r) => r.json("count") === events.length,
    });

    if (res.status !== 201) {
      errorRate.add(1);
    }
  });

  group("Analytics Queries", function () {
    const end = new Date().toISOString();
    const start = new Date(Date.now() - 3600000).toISOString();

    const queries = [
      { name: "event_type_counts", url: `${BASE_URL}/api/v1/analytics/counts/types?start=${start}&end=${end}` },
      { name: "source_counts", url: `${BASE_URL}/api/v1/analytics/counts/sources?start=${start}&end=${end}` },
      { name: "realtime_metrics", url: `${BASE_URL}/api/v1/analytics/realtime?window_seconds=300` },
    ];

    for (const q of queries) {
      const res = http.get(q.url, {
        headers,
        tags: { name: `analytics_${q.name}` },
      });
      analyticsQueryTrend.add(res.timings.duration);

      check(res, {
        [`${q.name} query successful`]: (r) => r.status === 200,
      });
    }
  });

  group("Dashboard Operations", function () {
    if (dashIds.length > 0) {
      const dashId = dashIds[0];
      const res = http.get(`${BASE_URL}/api/v1/dashboards/${dashId}`, {
        headers,
        tags: { name: "get_dashboard" },
      });
      dashboardTrend.add(res.timings.duration);

      check(res, {
        "get dashboard successful": (r) => r.status === 200,
        "dashboard has widgets": (r) => Array.isArray(r.json("widgets")),
      });
    }

    const listRes = http.get(`${BASE_URL}/api/v1/dashboards?page=1&page_size=10`, {
      headers,
      tags: { name: "list_dashboards" },
    });
    dashboardTrend.add(listRes.timings.duration);

    check(listRes, {
      "list dashboards successful": (r) => r.status === 200,
      "dashboard list has items property": (r) => r.json("items") !== undefined,
    });
  });

  sleep(randomInt(0.5, 2));
}

export function teardown(data) {
  if (data && data.token) {
    const headers = {
      Authorization: `Bearer ${data.token}`,
    };
    for (const dashId of data.dashboardIds || []) {
      http.del(`${BASE_URL}/api/v1/dashboards/${dashId}`, null, {
        headers,
        tags: { name: "cleanup_dashboard" },
      });
    }
  }
}

function randomChoice(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomInt(min, max) {
  return Math.random() * (max - min) + min;
}

function generatePayload() {
  const eventType = randomChoice([
    "page_view", "click", "signup", "purchase", "login", "logout", "error", "custom",
  ]);

  const payloads = {
    page_view: {
      url: randomChoice(["/home", "/products", "/pricing", "/docs", "/about"]),
      referrer: randomChoice(["https://google.com", "https://github.com", ""]),
      duration_ms: Math.floor(Math.random() * 60000),
      viewport_width: randomChoice([1920, 1440, 1366, 768]),
      viewport_height: randomChoice([1080, 900, 768, 812]),
    },
    click: {
      element: randomChoice(["button-submit", "nav-link", "cta-button", "menu-item"]),
      x_position: Math.floor(Math.random() * 1920),
      y_position: Math.floor(Math.random() * 1080),
    },
    signup: {
      method: randomChoice(["email", "google", "github"]),
      plan: randomChoice(["free", "starter", "pro"]),
    },
    purchase: {
      amount: parseFloat((Math.random() * 990 + 9.99).toFixed(2)),
      currency: randomChoice(["USD", "EUR", "GBP"]),
      items_count: Math.floor(Math.random() * 10) + 1,
    },
    login: {
      method: randomChoice(["password", "oauth", "saml"]),
      mfa_used: Math.random() > 0.5,
    },
    logout: {
      session_duration_minutes: Math.floor(Math.random() * 480),
    },
    error: {
      error_code: randomChoice(["ERR_404", "ERR_500", "ERR_TIMEOUT", "ERR_VALIDATION"]),
      error_message: "Load test generated error",
    },
    custom: {
      custom_key: `loadtest-${__VU}`,
      custom_value: Math.random() * 1000,
      tags: ["load-test", "performance"],
    },
  };

  return payloads[eventType] || {};
}
