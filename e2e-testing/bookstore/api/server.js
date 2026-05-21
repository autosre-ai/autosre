const express = require('express');
const { Pool } = require('pg');
const { v4: uuidv4 } = require('uuid');
const client = require('prom-client');

const app = express();
app.use(express.json());

// Database connection
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  database: process.env.DB_NAME || 'bookstore',
  user: process.env.DB_USER || 'bookstore',
  password: process.env.DB_PASSWORD || 'bookstore',
});

// Prometheus metrics
const register = new client.Registry();
client.collectDefaultMetrics({ register });

const httpRequestDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.001, 0.005, 0.015, 0.05, 0.1, 0.2, 0.5, 1, 2, 5],
  registers: [register],
});

const httpRequestsTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status_code'],
  registers: [register],
});

const httpErrorsTotal = new client.Counter({
  name: 'http_errors_total',
  help: 'Total number of HTTP errors',
  labelNames: ['method', 'route', 'status_code'],
  registers: [register],
});

const activeConnections = new client.Gauge({
  name: 'http_active_connections',
  help: 'Number of active HTTP connections',
  registers: [register],
});

const ordersTotal = new client.Counter({
  name: 'bookstore_orders_total',
  help: 'Total number of orders placed',
  registers: [register],
});

// Chaos engineering state
let chaosState = {
  errorRate: 0,
  latencyMs: 0,
  memoryLeak: false,
  leakedMemory: [],
};

// Memory leak array (for chaos testing)
const leakInterval = null;

// Middleware to track active connections
app.use((req, res, next) => {
  activeConnections.inc();
  res.on('finish', () => {
    activeConnections.dec();
  });
  next();
});

// Middleware for metrics and chaos injection
app.use(async (req, res, next) => {
  const start = Date.now();
  
  // Skip chaos for health/ready/metrics endpoints
  const skipChaos = ['/health', '/ready', '/metrics', '/chaos'].some(p => req.path.startsWith(p));
  
  if (!skipChaos) {
    // Inject latency if configured
    if (chaosState.latencyMs > 0) {
      await new Promise(resolve => setTimeout(resolve, chaosState.latencyMs));
    }
    
    // Inject errors if configured
    if (chaosState.errorRate > 0 && Math.random() < chaosState.errorRate) {
      const duration = (Date.now() - start) / 1000;
      httpRequestDuration.observe({ method: req.method, route: req.path, status_code: 500 }, duration);
      httpRequestsTotal.inc({ method: req.method, route: req.path, status_code: 500 });
      httpErrorsTotal.inc({ method: req.method, route: req.path, status_code: 500 });
      return res.status(500).json({ error: 'Chaos-injected error' });
    }
  }
  
  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    const route = req.route ? req.route.path : req.path;
    httpRequestDuration.observe({ method: req.method, route, status_code: res.statusCode }, duration);
    httpRequestsTotal.inc({ method: req.method, route, status_code: res.statusCode });
    if (res.statusCode >= 400) {
      httpErrorsTotal.inc({ method: req.method, route, status_code: res.statusCode });
    }
  });
  
  next();
});

// Health check - always returns OK if server is running
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// Readiness check - checks database connection
app.get('/ready', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ready', database: 'connected' });
  } catch (error) {
    res.status(503).json({ status: 'not ready', database: 'disconnected', error: error.message });
  }
});

// Get all books
app.get('/books', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM books ORDER BY id');
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get book by ID
app.get('/books/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const result = await pool.query('SELECT * FROM books WHERE id = $1', [id]);
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Book not found' });
    }
    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Create order
app.post('/orders', async (req, res) => {
  try {
    const { book_id, quantity, customer_email } = req.body;
    
    if (!book_id || !quantity || !customer_email) {
      return res.status(400).json({ error: 'book_id, quantity, and customer_email are required' });
    }
    
    // Check if book exists
    const bookResult = await pool.query('SELECT * FROM books WHERE id = $1', [book_id]);
    if (bookResult.rows.length === 0) {
      return res.status(404).json({ error: 'Book not found' });
    }
    
    const book = bookResult.rows[0];
    const total_price = book.price * quantity;
    const order_id = uuidv4();
    
    const result = await pool.query(
      `INSERT INTO orders (id, book_id, quantity, customer_email, total_price, status, created_at)
       VALUES ($1, $2, $3, $4, $5, 'pending', NOW())
       RETURNING *`,
      [order_id, book_id, quantity, customer_email, total_price]
    );
    
    ordersTotal.inc();
    res.status(201).json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get order by ID
app.get('/orders/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const result = await pool.query(
      `SELECT o.*, b.title as book_title, b.author as book_author
       FROM orders o
       JOIN books b ON o.book_id = b.id
       WHERE o.id = $1`,
      [id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Order not found' });
    }
    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Prometheus metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

// Chaos injection endpoints
app.post('/chaos/error-rate', (req, res) => {
  const rate = parseFloat(req.query.rate) || 0;
  if (rate < 0 || rate > 1) {
    return res.status(400).json({ error: 'Rate must be between 0 and 1' });
  }
  chaosState.errorRate = rate;
  res.json({ message: `Error rate set to ${rate * 100}%`, chaosState });
});

app.post('/chaos/latency', (req, res) => {
  const ms = parseInt(req.query.ms) || 0;
  if (ms < 0) {
    return res.status(400).json({ error: 'Latency must be non-negative' });
  }
  chaosState.latencyMs = ms;
  res.json({ message: `Latency set to ${ms}ms`, chaosState });
});

app.post('/chaos/memory-leak', (req, res) => {
  if (chaosState.memoryLeak) {
    return res.json({ message: 'Memory leak already active', chaosState });
  }
  
  chaosState.memoryLeak = true;
  
  // Start leaking memory - allocate 10MB every second
  const leakTimer = setInterval(() => {
    if (!chaosState.memoryLeak) {
      clearInterval(leakTimer);
      return;
    }
    // Allocate ~10MB of data
    const leak = Buffer.alloc(10 * 1024 * 1024);
    leak.fill('X');
    chaosState.leakedMemory.push(leak);
    console.log(`Memory leak: allocated ${chaosState.leakedMemory.length * 10}MB total`);
  }, 1000);
  
  res.json({ message: 'Memory leak started (10MB/second)', chaosState: { ...chaosState, leakedMB: 0 } });
});

app.post('/chaos/reset', (req, res) => {
  chaosState = {
    errorRate: 0,
    latencyMs: 0,
    memoryLeak: false,
    leakedMemory: [],
  };
  
  // Force garbage collection if available
  if (global.gc) {
    global.gc();
  }
  
  res.json({ message: 'Chaos state reset', chaosState });
});

app.get('/chaos/status', (req, res) => {
  res.json({
    ...chaosState,
    leakedMB: chaosState.leakedMemory.length * 10,
    leakedMemory: undefined,
  });
});

// Start server
const PORT = process.env.PORT || 8080;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Bookstore API listening on port ${PORT}`);
});
