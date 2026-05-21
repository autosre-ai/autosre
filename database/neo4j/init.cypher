// AutoSRE Knowledge Graph - Neo4j Initialization Script
// Run with: cat init.cypher | cypher-shell -u neo4j -p <password>

// ============================================================================
// CONSTRAINTS - Ensure data integrity
// ============================================================================

// Service constraints
CREATE CONSTRAINT service_id IF NOT EXISTS FOR (s:Service) REQUIRE s.id IS UNIQUE;

// Infrastructure constraints
CREATE CONSTRAINT pod_id IF NOT EXISTS FOR (p:Pod) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT namespace_id IF NOT EXISTS FOR (ns:Namespace) REQUIRE ns.id IS UNIQUE;
CREATE CONSTRAINT database_id IF NOT EXISTS FOR (d:Database) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT cache_id IF NOT EXISTS FOR (c:Cache) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT queue_id IF NOT EXISTS FOR (q:MessageQueue) REQUIRE q.id IS UNIQUE;

// Operational constraints
CREATE CONSTRAINT alert_id IF NOT EXISTS FOR (a:Alert) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT incident_id IF NOT EXISTS FOR (i:Incident) REQUIRE i.id IS UNIQUE;

// ============================================================================
// INDEXES - Optimize common queries
// ============================================================================

// Service indexes
CREATE INDEX service_name IF NOT EXISTS FOR (s:Service) ON (s.name);
CREATE INDEX service_namespace IF NOT EXISTS FOR (s:Service) ON (s.namespace);
CREATE INDEX service_tier IF NOT EXISTS FOR (s:Service) ON (s.tier);
CREATE INDEX service_status IF NOT EXISTS FOR (s:Service) ON (s.status);
CREATE INDEX service_team IF NOT EXISTS FOR (s:Service) ON (s.team);

// Infrastructure indexes
CREATE INDEX pod_namespace IF NOT EXISTS FOR (p:Pod) ON (p.namespace);
CREATE INDEX pod_status IF NOT EXISTS FOR (p:Pod) ON (p.status);
CREATE INDEX node_cluster IF NOT EXISTS FOR (n:Node) ON (n.cluster);
CREATE INDEX node_zone IF NOT EXISTS FOR (n:Node) ON (n.zone);

// Operational indexes
CREATE INDEX alert_status IF NOT EXISTS FOR (a:Alert) ON (a.status);
CREATE INDEX alert_severity IF NOT EXISTS FOR (a:Alert) ON (a.severity);
CREATE INDEX incident_status IF NOT EXISTS FOR (i:Incident) ON (i.status);
CREATE INDEX incident_severity IF NOT EXISTS FOR (i:Incident) ON (i.severity);

// ============================================================================
// EXAMPLE TOPOLOGY - E-commerce Platform
// ============================================================================

// Clear existing data (comment out in production!)
// MATCH (n) DETACH DELETE n;

// --- Namespaces ---
MERGE (ns:Namespace {id: 'production'})
SET ns.name = 'production',
    ns.environment = 'production',
    ns.cluster = 'main-cluster';

// --- Tier 0: Mission Critical Services ---

MERGE (frontend:Service {id: 'frontend'})
SET frontend.name = 'frontend',
    frontend.namespace = 'production',
    frontend.tier = 'tier_1',
    frontend.status = 'healthy',
    frontend.team = 'platform',
    frontend.owner = 'alice@company.com',
    frontend.description = 'Main web frontend (React)',
    frontend.language = 'typescript',
    frontend.framework = 'react',
    frontend.replicas = 3,
    frontend.slo_availability = 99.9,
    frontend.slo_latency_p99_ms = 200,
    frontend.created_at = datetime(),
    frontend.updated_at = datetime();

MERGE (api_gateway:Service {id: 'api-gateway'})
SET api_gateway.name = 'api-gateway',
    api_gateway.namespace = 'production',
    api_gateway.tier = 'tier_0',
    api_gateway.status = 'healthy',
    api_gateway.team = 'platform',
    api_gateway.owner = 'bob@company.com',
    api_gateway.description = 'API Gateway / BFF - handles routing, auth, rate limiting',
    api_gateway.language = 'go',
    api_gateway.framework = 'gin',
    api_gateway.replicas = 5,
    api_gateway.slo_availability = 99.99,
    api_gateway.slo_latency_p99_ms = 50,
    api_gateway.created_at = datetime(),
    api_gateway.updated_at = datetime();

MERGE (auth:Service {id: 'auth-service'})
SET auth.name = 'auth-service',
    auth.namespace = 'production',
    auth.tier = 'tier_0',
    auth.status = 'healthy',
    auth.team = 'security',
    auth.owner = 'carol@company.com',
    auth.description = 'Authentication and authorization (OAuth2, JWT)',
    auth.language = 'go',
    auth.framework = 'gin',
    auth.replicas = 3,
    auth.slo_availability = 99.99,
    auth.slo_latency_p99_ms = 100,
    auth.created_at = datetime(),
    auth.updated_at = datetime();

MERGE (order:Service {id: 'order-service'})
SET order.name = 'order-service',
    order.namespace = 'production',
    order.tier = 'tier_0',
    order.status = 'healthy',
    order.team = 'orders',
    order.owner = 'dave@company.com',
    order.description = 'Order processing and management',
    order.language = 'java',
    order.framework = 'spring-boot',
    order.replicas = 4,
    order.slo_availability = 99.95,
    order.slo_latency_p99_ms = 500,
    order.created_at = datetime(),
    order.updated_at = datetime();

MERGE (payment:Service {id: 'payment-service'})
SET payment.name = 'payment-service',
    payment.namespace = 'production',
    payment.tier = 'tier_0',
    payment.status = 'healthy',
    payment.team = 'payments',
    payment.owner = 'eve@company.com',
    payment.description = 'Payment processing (Stripe, PayPal)',
    payment.language = 'java',
    payment.framework = 'spring-boot',
    payment.replicas = 3,
    payment.slo_availability = 99.99,
    payment.slo_latency_p99_ms = 1000,
    payment.created_at = datetime(),
    payment.updated_at = datetime();

// --- Tier 1: Business Critical Services ---

MERGE (user:Service {id: 'user-service'})
SET user.name = 'user-service',
    user.namespace = 'production',
    user.tier = 'tier_1',
    user.status = 'healthy',
    user.team = 'users',
    user.owner = 'frank@company.com',
    user.description = 'User management and profiles',
    user.language = 'python',
    user.framework = 'fastapi',
    user.replicas = 2,
    user.slo_availability = 99.9,
    user.slo_latency_p99_ms = 200,
    user.created_at = datetime(),
    user.updated_at = datetime();

MERGE (product:Service {id: 'product-service'})
SET product.name = 'product-service',
    product.namespace = 'production',
    product.tier = 'tier_1',
    product.status = 'healthy',
    product.team = 'catalog',
    product.owner = 'grace@company.com',
    product.description = 'Product catalog and inventory',
    product.language = 'python',
    product.framework = 'fastapi',
    product.replicas = 2,
    product.slo_availability = 99.9,
    product.slo_latency_p99_ms = 300,
    product.created_at = datetime(),
    product.updated_at = datetime();

MERGE (cart:Service {id: 'cart-service'})
SET cart.name = 'cart-service',
    cart.namespace = 'production',
    cart.tier = 'tier_1',
    cart.status = 'healthy',
    cart.team = 'orders',
    cart.owner = 'dave@company.com',
    cart.description = 'Shopping cart management',
    cart.language = 'go',
    cart.framework = 'gin',
    cart.replicas = 2,
    cart.slo_availability = 99.9,
    cart.slo_latency_p99_ms = 100,
    cart.created_at = datetime(),
    cart.updated_at = datetime();

// --- Tier 2: Important Services ---

MERGE (inventory:Service {id: 'inventory-service'})
SET inventory.name = 'inventory-service',
    inventory.namespace = 'production',
    inventory.tier = 'tier_2',
    inventory.status = 'healthy',
    inventory.team = 'warehouse',
    inventory.owner = 'henry@company.com',
    inventory.description = 'Inventory tracking and management',
    inventory.language = 'python',
    inventory.framework = 'django',
    inventory.replicas = 2,
    inventory.slo_availability = 99.5,
    inventory.slo_latency_p99_ms = 500,
    inventory.created_at = datetime(),
    inventory.updated_at = datetime();

MERGE (search:Service {id: 'search-service'})
SET search.name = 'search-service',
    search.namespace = 'production',
    search.tier = 'tier_2',
    search.status = 'healthy',
    search.team = 'search',
    search.owner = 'ivy@company.com',
    search.description = 'Product search (Elasticsearch)',
    search.language = 'java',
    search.framework = 'spring-boot',
    search.replicas = 2,
    search.slo_availability = 99.5,
    search.slo_latency_p99_ms = 200,
    search.created_at = datetime(),
    search.updated_at = datetime();

MERGE (notification:Service {id: 'notification-service'})
SET notification.name = 'notification-service',
    notification.namespace = 'production',
    notification.tier = 'tier_2',
    notification.status = 'healthy',
    notification.team = 'platform',
    notification.owner = 'jack@company.com',
    notification.description = 'Email, SMS, Push notifications',
    notification.language = 'python',
    notification.framework = 'celery',
    notification.replicas = 2,
    notification.slo_availability = 99.0,
    notification.slo_latency_p99_ms = 5000,
    notification.created_at = datetime(),
    notification.updated_at = datetime();

MERGE (recommendation:Service {id: 'recommendation-service'})
SET recommendation.name = 'recommendation-service',
    recommendation.namespace = 'production',
    recommendation.tier = 'tier_2',
    recommendation.status = 'healthy',
    recommendation.team = 'ml',
    recommendation.owner = 'kate@company.com',
    recommendation.description = 'Product recommendations (ML)',
    recommendation.language = 'python',
    recommendation.framework = 'fastapi',
    recommendation.replicas = 2,
    recommendation.slo_availability = 99.0,
    recommendation.slo_latency_p99_ms = 500,
    recommendation.created_at = datetime(),
    recommendation.updated_at = datetime();

// --- Tier 3: Standard Services ---

MERGE (analytics:Service {id: 'analytics-service'})
SET analytics.name = 'analytics-service',
    analytics.namespace = 'production',
    analytics.tier = 'tier_3',
    analytics.status = 'healthy',
    analytics.team = 'analytics',
    analytics.owner = 'leo@company.com',
    analytics.description = 'Business analytics and reporting',
    analytics.language = 'python',
    analytics.framework = 'flask',
    analytics.replicas = 1,
    analytics.slo_availability = 99.0,
    analytics.slo_latency_p99_ms = 2000,
    analytics.created_at = datetime(),
    analytics.updated_at = datetime();

// ============================================================================
// SERVICE DEPENDENCIES
// ============================================================================

// Frontend dependencies
MATCH (source:Service {id: 'frontend'}), (target:Service {id: 'api-gateway'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'https',
    d.port = 443,
    d.is_critical = true,
    d.calls_per_minute = 5000,
    d.latency_p99_ms = 50,
    d.created_at = datetime();

// API Gateway dependencies
MATCH (source:Service {id: 'api-gateway'}), (target:Service {id: 'auth-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'grpc',
    d.port = 50051,
    d.is_critical = true,
    d.calls_per_minute = 10000,
    d.latency_p99_ms = 20,
    d.created_at = datetime();

MATCH (source:Service {id: 'api-gateway'}), (target:Service {id: 'user-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.calls_per_minute = 3000,
    d.latency_p99_ms = 100,
    d.created_at = datetime();

MATCH (source:Service {id: 'api-gateway'}), (target:Service {id: 'product-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.calls_per_minute = 4000,
    d.latency_p99_ms = 150,
    d.created_at = datetime();

MATCH (source:Service {id: 'api-gateway'}), (target:Service {id: 'cart-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.calls_per_minute = 2000,
    d.latency_p99_ms = 50,
    d.created_at = datetime();

MATCH (source:Service {id: 'api-gateway'}), (target:Service {id: 'order-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = true,
    d.calls_per_minute = 1500,
    d.latency_p99_ms = 300,
    d.created_at = datetime();

MATCH (source:Service {id: 'api-gateway'}), (target:Service {id: 'search-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.has_fallback = true,
    d.calls_per_minute = 2500,
    d.latency_p99_ms = 100,
    d.created_at = datetime();

// Auth service dependencies
MATCH (source:Service {id: 'auth-service'}), (target:Service {id: 'user-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'grpc',
    d.port = 50051,
    d.is_critical = false,
    d.calls_per_minute = 2000,
    d.latency_p99_ms = 50,
    d.created_at = datetime();

// Product service dependencies
MATCH (source:Service {id: 'product-service'}), (target:Service {id: 'inventory-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.calls_per_minute = 1000,
    d.latency_p99_ms = 200,
    d.created_at = datetime();

MATCH (source:Service {id: 'product-service'}), (target:Service {id: 'search-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.has_fallback = true,
    d.calls_per_minute = 500,
    d.latency_p99_ms = 100,
    d.created_at = datetime();

MATCH (source:Service {id: 'product-service'}), (target:Service {id: 'recommendation-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.has_fallback = true,
    d.calls_per_minute = 800,
    d.latency_p99_ms = 300,
    d.created_at = datetime();

// Cart service dependencies
MATCH (source:Service {id: 'cart-service'}), (target:Service {id: 'product-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.calls_per_minute = 500,
    d.latency_p99_ms = 100,
    d.created_at = datetime();

MATCH (source:Service {id: 'cart-service'}), (target:Service {id: 'inventory-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.calls_per_minute = 300,
    d.latency_p99_ms = 150,
    d.created_at = datetime();

// Order service dependencies
MATCH (source:Service {id: 'order-service'}), (target:Service {id: 'payment-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'grpc',
    d.port = 50051,
    d.is_critical = true,
    d.calls_per_minute = 500,
    d.latency_p99_ms = 500,
    d.created_at = datetime();

MATCH (source:Service {id: 'order-service'}), (target:Service {id: 'inventory-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = true,
    d.calls_per_minute = 400,
    d.latency_p99_ms = 200,
    d.created_at = datetime();

MATCH (source:Service {id: 'order-service'}), (target:Service {id: 'user-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.calls_per_minute = 200,
    d.latency_p99_ms = 100,
    d.created_at = datetime();

MATCH (source:Service {id: 'order-service'}), (target:Service {id: 'notification-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'async',
    d.protocol = 'kafka',
    d.port = 9092,
    d.is_critical = false,
    d.calls_per_minute = 300,
    d.created_at = datetime();

// Recommendation service dependencies
MATCH (source:Service {id: 'recommendation-service'}), (target:Service {id: 'user-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'sync',
    d.protocol = 'http',
    d.port = 8080,
    d.is_critical = false,
    d.calls_per_minute = 400,
    d.latency_p99_ms = 100,
    d.created_at = datetime();

MATCH (source:Service {id: 'recommendation-service'}), (target:Service {id: 'analytics-service'})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.dependency_type = 'async',
    d.protocol = 'kafka',
    d.port = 9092,
    d.is_critical = false,
    d.calls_per_minute = 100,
    d.created_at = datetime();

// ============================================================================
// INFRASTRUCTURE
// ============================================================================

// Databases
MERGE (postgres_main:Database {id: 'postgres-main'})
SET postgres_main.name = 'postgres-main',
    postgres_main.engine = 'postgresql',
    postgres_main.version = '15.4',
    postgres_main.host = 'postgres-main.db.internal',
    postgres_main.port = 5432,
    postgres_main.is_primary = true,
    postgres_main.replicas = 2,
    postgres_main.max_connections = 200,
    postgres_main.storage_gb = 500,
    postgres_main.created_at = datetime();

MERGE (postgres_auth:Database {id: 'postgres-auth'})
SET postgres_auth.name = 'postgres-auth',
    postgres_auth.engine = 'postgresql',
    postgres_auth.version = '15.4',
    postgres_auth.host = 'postgres-auth.db.internal',
    postgres_auth.port = 5432,
    postgres_auth.is_primary = true,
    postgres_auth.replicas = 2,
    postgres_auth.max_connections = 100,
    postgres_auth.storage_gb = 50,
    postgres_auth.created_at = datetime();

MERGE (postgres_orders:Database {id: 'postgres-orders'})
SET postgres_orders.name = 'postgres-orders',
    postgres_orders.engine = 'postgresql',
    postgres_orders.version = '15.4',
    postgres_orders.host = 'postgres-orders.db.internal',
    postgres_orders.port = 5432,
    postgres_orders.is_primary = true,
    postgres_orders.replicas = 2,
    postgres_orders.max_connections = 150,
    postgres_orders.storage_gb = 1000,
    postgres_orders.created_at = datetime();

// Link services to databases
MATCH (s:Service {id: 'user-service'}), (db:Database {id: 'postgres-main'})
MERGE (s)-[r:USES_DATABASE]->(db)
SET r.connection_pool_size = 20,
    r.read_only = false;

MATCH (s:Service {id: 'product-service'}), (db:Database {id: 'postgres-main'})
MERGE (s)-[r:USES_DATABASE]->(db)
SET r.connection_pool_size = 30,
    r.read_only = false;

MATCH (s:Service {id: 'auth-service'}), (db:Database {id: 'postgres-auth'})
MERGE (s)-[r:USES_DATABASE]->(db)
SET r.connection_pool_size = 20,
    r.read_only = false;

MATCH (s:Service {id: 'order-service'}), (db:Database {id: 'postgres-orders'})
MERGE (s)-[r:USES_DATABASE]->(db)
SET r.connection_pool_size = 40,
    r.read_only = false;

MATCH (s:Service {id: 'payment-service'}), (db:Database {id: 'postgres-orders'})
MERGE (s)-[r:USES_DATABASE]->(db)
SET r.connection_pool_size = 20,
    r.read_only = false;

MATCH (s:Service {id: 'inventory-service'}), (db:Database {id: 'postgres-main'})
MERGE (s)-[r:USES_DATABASE]->(db)
SET r.connection_pool_size = 20,
    r.read_only = false;

// Caches
MERGE (redis_main:Cache {id: 'redis-main'})
SET redis_main.name = 'redis-main',
    redis_main.engine = 'redis',
    redis_main.version = '7.2',
    redis_main.host = 'redis-main.cache.internal',
    redis_main.port = 6379,
    redis_main.cluster_mode = true,
    redis_main.node_count = 6,
    redis_main.memory_mb = 16384,
    redis_main.created_at = datetime();

MERGE (redis_session:Cache {id: 'redis-session'})
SET redis_session.name = 'redis-session',
    redis_session.engine = 'redis',
    redis_session.version = '7.2',
    redis_session.host = 'redis-session.cache.internal',
    redis_session.port = 6379,
    redis_session.cluster_mode = false,
    redis_session.node_count = 3,
    redis_session.memory_mb = 8192,
    redis_session.created_at = datetime();

// Link services to caches
MATCH (s:Service {id: 'api-gateway'}), (c:Cache {id: 'redis-main'})
MERGE (s)-[r:USES_CACHE]->(c);

MATCH (s:Service {id: 'auth-service'}), (c:Cache {id: 'redis-session'})
MERGE (s)-[r:USES_CACHE]->(c);

MATCH (s:Service {id: 'user-service'}), (c:Cache {id: 'redis-main'})
MERGE (s)-[r:USES_CACHE]->(c);

MATCH (s:Service {id: 'cart-service'}), (c:Cache {id: 'redis-main'})
MERGE (s)-[r:USES_CACHE]->(c);

MATCH (s:Service {id: 'product-service'}), (c:Cache {id: 'redis-main'})
MERGE (s)-[r:USES_CACHE]->(c);

// Message Queues
MERGE (kafka:MessageQueue {id: 'kafka-main'})
SET kafka.name = 'kafka-main',
    kafka.engine = 'kafka',
    kafka.version = '3.5',
    kafka.brokers = ['kafka-0.kafka.internal:9092', 'kafka-1.kafka.internal:9092', 'kafka-2.kafka.internal:9092'],
    kafka.topic_count = 50,
    kafka.partition_count = 150,
    kafka.created_at = datetime();

// Link services to message queue
MATCH (s:Service {id: 'order-service'}), (q:MessageQueue {id: 'kafka-main'})
MERGE (s)-[r:PUBLISHES_TO]->(q)
SET r.topics = ['orders.created', 'orders.updated', 'orders.completed'];

MATCH (s:Service {id: 'notification-service'}), (q:MessageQueue {id: 'kafka-main'})
MERGE (s)-[r:SUBSCRIBES_TO]->(q)
SET r.topics = ['orders.created', 'orders.completed', 'users.created'];

MATCH (s:Service {id: 'analytics-service'}), (q:MessageQueue {id: 'kafka-main'})
MERGE (s)-[r:SUBSCRIBES_TO]->(q)
SET r.topics = ['orders.created', 'orders.completed', 'products.viewed'];

MATCH (s:Service {id: 'inventory-service'}), (q:MessageQueue {id: 'kafka-main'})
MERGE (s)-[r:SUBSCRIBES_TO]->(q)
SET r.topics = ['orders.completed'];

// ============================================================================
// SUMMARY
// ============================================================================

// Print summary
MATCH (s:Service) WITH count(s) as services
MATCH ()-[d:DEPENDS_ON]->() WITH services, count(d) as dependencies
MATCH (db:Database) WITH services, dependencies, count(db) as databases
MATCH (c:Cache) WITH services, dependencies, databases, count(c) as caches
MATCH (q:MessageQueue) WITH services, dependencies, databases, caches, count(q) as queues
RETURN 
    services as total_services,
    dependencies as total_dependencies,
    databases as total_databases,
    caches as total_caches,
    queues as total_queues;
