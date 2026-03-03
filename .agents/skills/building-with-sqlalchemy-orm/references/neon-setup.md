# Neon PostgreSQL Setup & Configuration

Source: [Neon Official Docs](https://neon.com/docs/)

## What is Neon?

Neon is a **serverless PostgreSQL database**:
- Fully compatible with PostgreSQL 15+
- Auto-scales compute up/down based on demand
- Scales to zero when idle (save costs)
- Native database branching (like Git for databases)
- Read-only replicas for scaling read traffic

## Getting Started with Neon

### Step 1: Create Neon Account

1. Go to [neon.com](https://neon.com/)
2. Sign up (free tier includes 3 projects)
3. Create a new project
4. Choose region closest to your app

### Step 2: Get Connection String

In Neon dashboard:
1. Click your project
2. Go to "Connection" tab
3. Copy the **PostgreSQL connection string**
4. Format: `postgresql+psycopg2://user:password@ep-ABC123.neon.tech/dbname?sslmode=require`

### Step 3: Store in Environment

Create `.env` file (never commit this):

```env
DATABASE_URL=postgresql+psycopg2://user:password@ep-ABC123.neon.tech/dbname?sslmode=require
```

Load in Python:

```python
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
```

## Connection String Breakdown

```
postgresql+psycopg2://user:password@host/dbname?sslmode=require
│                     │    │          │          │
│                     │    │          │          └─ SSL required (Neon enforces)
│                     │    │          └─ Database name
│                     │    └─ Password
│                     └─ Username
└─ Driver: psycopg2 (PostgreSQL driver for Python)
```

## Neon-Specific Features

### 1. Auto-Scaling (Serverless)

Neon automatically scales compute resources:
- **Scale up**: When traffic increases
- **Scale down**: When traffic decreases
- **Scale to zero**: When idle for 5+ minutes (no running queries)

**For students**: No need to provision servers. SQLAlchemy works the same.

### 2. Database Branching

Create branches for development/testing:

```bash
# In Neon dashboard, create a branch of main
# Gives you isolated copy of production data
```

Useful for:
- Testing migrations before production
- Developing features without affecting main
- Teaching with safe experimental database

### 3. Read Replicas

Create read-only replicas for scaling read queries:

```python
# Main database: write operations
main_engine = create_engine(main_connection_string)

# Replica: read-only queries
replica_engine = create_engine(replica_connection_string)

# Route heavy queries to replica
with Session(replica_engine) as session:
    reports = session.query(Expense).filter(...).all()
```

### 4. Cost Benefits

Neon scales compute to match workload:
- **Development**: Scale to zero when not in use
- **Production**: Scale up only when needed
- **Spike handling**: Auto-scales for traffic surges

**Real-world example**: With traditional managed PostgreSQL, you pay for a fixed server 24/7. With Neon, you pay only for what you use.

## SSL/TLS (Required by Neon)

Neon requires encrypted connections (`sslmode=require`):

```python
# This is already in your connection string
DATABASE_URL=postgresql+psycopg2://...?sslmode=require
```

SQLAlchemy with psycopg2 handles this automatically. No additional code needed.

## Connection Pooling for Neon

Since Neon scales compute, connection pooling is important:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,              # Keep 5 connections open
    max_overflow=10,          # Allow 10 more if needed
    pool_recycle=3600,        # Recycle after 1 hour
    pool_pre_ping=True,       # Test before use
    echo=False
)
```

**Why this matters for Neon**:
- **pool_size=5**: Enough for typical app, doesn't waste Neon compute
- **max_overflow=10**: Handles traffic spikes
- **pool_recycle=3600**: Neon pauses idle connections; recycle them
- **pool_pre_ping=True**: Verify connection is alive before use

## Environment Variables

Best practice for production:

```python
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env file")

# Don't hardcode!
# ❌ engine = create_engine("postgresql+psycopg2://user:pass@...")
# ✅ engine = create_engine(DATABASE_URL)
```

In production (no `.env` file), set via environment:

```bash
# Heroku, Vercel, AWS, etc.
export DATABASE_URL=postgresql+psycopg2://...
```

## Neon vs Traditional PostgreSQL

| Feature | Neon | Traditional (RDS, DigitalOcean) |
|---------|------|-------|
| **Setup time** | 2 minutes | 20-30 minutes |
| **Scaling** | Automatic | Manual (resize instance) |
| **Idle cost** | $0 (scales to zero) | Fixed monthly cost |
| **Connections** | Limited by compute tier | Limited by instance size |
| **Backups** | Automatic | Optional, extra cost |
| **Branching** | Built-in (Git-like) | Not available |
| **Learning curve** | Very low | Medium |

## Debugging Connection Issues

### Issue: `OperationalError: could not connect to server`

**Causes**:
1. Wrong connection string
2. Neon project not active
3. IP not whitelisted (though Neon doesn't use IP allowlists)
4. Network issue

**Fix**:
```python
# Test connection
from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("Connected!")
except Exception as e:
    print(f"Connection failed: {e}")
```

### Issue: `psycopg2.OperationalError: FATAL: invalid password`

**Cause**: Wrong password in connection string

**Fix**:
1. Go to Neon dashboard
2. Click "Reset password" on your user
3. Copy new connection string
4. Update `.env` file

### Issue: `psycopg2.InterfaceError: server closed the connection unexpectedly`

**Cause**: Connection idle timeout (Neon pauses after 5 minutes of inactivity)

**Fix**: Enable `pool_pre_ping=True`:

```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True  # This fixes it!
)
```

## Monitoring in Neon

In Neon dashboard:
- **Monitoring** tab shows compute usage
- **Queries** tab shows recent queries
- **Insights** tab shows performance metrics

For students: Shows real-world impact of their queries and scaling.

## Cost Tracking

Free tier includes:
- 3 projects
- 3 GB of storage
- Shared compute

For teaching:
- Perfect for learning (free!)
- Each student gets own project
- No credit card needed (for free tier)

## References

- [Neon Getting Started](https://neon.com/docs/getting-started/setting-up-a-local-development-environment)
- [Neon Connection Strings](https://neon.com/docs/reference/connection-string)
- [Neon Branching](https://neon.com/docs/guides/branching)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/current/)
