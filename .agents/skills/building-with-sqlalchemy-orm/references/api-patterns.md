# SQLAlchemy ORM API Patterns (Official Documentation)

Source: [SQLAlchemy 2.0+ Official Docs](https://docs.sqlalchemy.org/en/20/orm/)

## Session Management (Unit of Work Pattern)

### Context Manager (Recommended)
```python
from sqlalchemy.orm import Session

with Session(engine) as session:
    # All operations here
    user = session.query(User).first()
    session.add(new_user)
    session.commit()
    # Automatically closes session on exit
```

### Manual Management
```python
session = Session(engine)
try:
    # Operations here
    session.commit()
finally:
    session.close()
```

## Model Definition

### Basic Model
```python
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True)
    balance = Column(Float, default=0.0)
```

### Column Types
- `Integer`: Whole numbers
- `String(n)`: Text with max length
- `Float`: Decimal numbers
- `DateTime`: Timestamps
- `Boolean`: True/False
- `JSON`: Structured data
- `Date`: Calendar dates

### Constraints
```python
Column(String(50), nullable=False)        # Required field
Column(String(100), unique=True)          # No duplicates
Column(Integer, default=0)                # Default value
Column(Integer, primary_key=True)         # Primary key
Column(Integer, ForeignKey('other.id'))   # Foreign key
```

## CRUD Operations

### Create
```python
new_user = User(name="Alice", email="alice@example.com")
session.add(new_user)
session.commit()
print(new_user.id)  # ID auto-generated
```

### Read (Query)
```python
# Get all
all_users = session.query(User).all()

# Get first
first_user = session.query(User).first()

# Get by ID
user = session.query(User).filter(User.id == 1).first()

# Get by other field
user = session.query(User).filter_by(email="alice@example.com").first()
```

### Update
```python
user = session.query(User).filter(User.id == 1).first()
user.name = "Alice Smith"
session.commit()  # Changes persisted
```

### Delete
```python
user = session.query(User).filter(User.id == 1).first()
session.delete(user)
session.commit()
```

## Relationships

### One-to-Many
```python
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    posts = relationship("Post", back_populates="author")

class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey('users.id'))
    author = relationship("User", back_populates="posts")

# Usage
user = session.query(User).first()
print(user.posts)  # All posts by this user
```

### Many-to-Many
```python
from sqlalchemy import Table

# Association table
user_role = Table(
    'user_role',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('role_id', Integer, ForeignKey('roles.id'))
)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    roles = relationship("Role", secondary=user_role)

class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
```

## Advanced Querying

### Filtering
```python
# Single condition
session.query(User).filter(User.age > 18).all()

# Multiple conditions (AND)
session.query(User).filter(User.age > 18, User.active == True).all()

# OR conditions
from sqlalchemy import or_
session.query(User).filter(or_(User.age > 18, User.premium == True)).all()

# IN operator
session.query(User).filter(User.id.in_([1, 2, 3])).all()
```

### Ordering & Limiting
```python
# Order ascending
session.query(User).order_by(User.name).all()

# Order descending
session.query(User).order_by(User.age.desc()).all()

# Limit results
session.query(User).limit(10).all()

# Offset (pagination)
session.query(User).offset(20).limit(10).all()
```

### Joins
```python
# Inner join (only matching records)
session.query(User, Post).join(Post).all()

# Left join (all users, even without posts)
session.query(User).outerjoin(Post).all()

# Explicit join condition
session.query(User).join(Post, User.id == Post.author_id).all()
```

### Aggregation
```python
from sqlalchemy import func

# Count
count = session.query(func.count(User.id)).scalar()

# Sum
total = session.query(func.sum(Order.amount)).scalar()

# Average
avg_age = session.query(func.avg(User.age)).scalar()

# Group by
results = session.query(
    Category.name,
    func.count(Product.id).label('product_count')
).join(Product).group_by(Category.name).all()
```

## Transaction Control

### Explicit Commit
```python
try:
    session.add(new_user)
    session.commit()
except Exception as e:
    session.rollback()
    print(f"Error: {e}")
```

### Savepoints (Nested Transactions)
```python
with session.begin_nested():
    # This block can be rolled back independently
    session.add(risky_operation)
    session.commit()  # If error, only this block rolls back
```

### Autoflush Control
```python
# Disable autoflush (manual control)
session.autoflush = False
session.add(user)
session.flush()  # Send to database but don't commit
session.commit()
```

## Engine Configuration

### Basic Engine
```python
from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg2://user:password@localhost/dbname")
```

### Connection Pooling
```python
from sqlalchemy.pool import QueuePool

engine = create_engine(
    "postgresql+psycopg2://user:password@host/dbname",
    poolclass=QueuePool,
    pool_size=10,           # Number of connections to keep
    max_overflow=20,        # Additional connections when needed
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_pre_ping=True      # Test connection before use
)
```

### Debugging
```python
# Enable SQL logging
engine = create_engine(DATABASE_URL, echo=True)

# Check pool status
print(engine.pool.size())
print(engine.pool.checkedout())
```

## References

- [SQLAlchemy ORM Quickstart](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [Session Documentation](https://docs.sqlalchemy.org/en/20/orm/session.html)
- [Relationships Documentation](https://docs.sqlalchemy.org/en/20/orm/relationships.html)
- [Query API](https://docs.sqlalchemy.org/en/20/orm/queryguide.html)
