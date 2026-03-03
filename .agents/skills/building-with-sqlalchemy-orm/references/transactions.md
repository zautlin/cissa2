# Transaction Handling & Session Management

## Core Principle: Atomicity

A transaction is **all or nothing**: either all database operations succeed, or none of them do.

```python
# Good: All succeed or all roll back
try:
    session.add(expense)
    session.add(category)
    session.commit()  # Both saved
except Exception:
    session.rollback()  # Both discarded
```

```python
# Bad: Partial save (corrupts data)
session.add(expense)
session.commit()
session.add(category)
session.commit()  # What if this fails? Expense is orphaned
```

## Session Lifecycle

### Context Manager (Recommended)

```python
from sqlalchemy.orm import Session

with Session(engine) as session:
    # Session is open
    user = session.query(User).first()
    user.name = "Updated"
    session.commit()
# Session is automatically closed here
```

**Advantages**:
- Automatic cleanup (session closed even if error)
- Clear scope
- Can't forget to close

### Manual Management

```python
session = Session(engine)
try:
    user = session.query(User).first()
    session.commit()
except Exception as e:
    session.rollback()
finally:
    session.close()
```

## Transaction Patterns

### Pattern 1: Simple CRUD with Commit

```python
def create_user(name):
    with Session(engine) as session:
        user = User(name=name)
        session.add(user)
        session.commit()
        return user.id
```

### Pattern 2: Read-Modify-Write

```python
def update_user_balance(user_id, amount):
    with Session(engine) as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        user.balance += amount
        session.commit()
        return user.balance
```

### Pattern 3: Multi-Step Transaction (All or Nothing)

```python
def transfer_money(from_user_id, to_user_id, amount):
    """Transfer money between users - must succeed completely."""
    with Session(engine) as session:
        try:
            from_user = session.query(User).filter(User.id == from_user_id).first()
            to_user = session.query(User).filter(User.id == to_user_id).first()

            if not from_user or not to_user:
                raise ValueError("User not found")
            if from_user.balance < amount:
                raise ValueError("Insufficient funds")

            from_user.balance -= amount
            to_user.balance += amount

            session.commit()  # Both changes saved or none
            return True
        except Exception as e:
            session.rollback()  # Both changes discarded
            print(f"Transfer failed: {e}")
            return False
```

### Pattern 4: Bulk Operations

```python
def delete_all_expenses(user_id):
    """Delete all expenses for a user in one transaction."""
    with Session(engine) as session:
        try:
            session.query(Expense).filter(Expense.user_id == user_id).delete()
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
```

### Pattern 5: Savepoints (Nested Transactions)

```python
def process_batch(items):
    """Process items, rolling back only failed ones."""
    with Session(engine) as session:
        results = []
        for item in items:
            try:
                with session.begin_nested():  # Inner transaction
                    result = process_item(session, item)
                    results.append(result)
                    session.flush()  # Commit this item
            except Exception as e:
                session.rollback()  # Only this item rolls back
                results.append({"error": str(e)})

        session.commit()  # Finalize all successful items
        return results
```

## Common Errors & Solutions

### Error 1: Forgetting to Commit

```python
# ❌ Wrong: Changes not saved
def create_expense(description, amount):
    with Session(engine) as session:
        expense = Expense(description=description, amount=amount)
        session.add(expense)
        # Forgot session.commit()!
        return expense

# ✅ Right: Changes saved
def create_expense(description, amount):
    with Session(engine) as session:
        expense = Expense(description=description, amount=amount)
        session.add(expense)
        session.commit()  # Changes now saved
        return expense
```

### Error 2: Using Detached Objects

```python
# ❌ Wrong: Object becomes detached after session closes
def get_expense():
    with Session(engine) as session:
        return session.query(Expense).first()

expense = get_expense()
print(expense.description)  # Works (data already loaded)
print(expense.category.name)  # Error! Category relationship not loaded, session closed
```

**Solutions**:

```python
# Solution 1: Load relationships before closing session
def get_expense_with_category():
    with Session(engine) as session:
        expense = session.query(Expense).first()
        category = expense.category  # Load before session closes
        return expense

# Solution 2: Use eager loading
def get_expense_eager():
    from sqlalchemy.orm import joinedload
    with Session(engine) as session:
        expense = session.query(Expense).options(
            joinedload(Expense.category)
        ).first()
        return expense  # Category already loaded

# Solution 3: Serialize to dict (recommended)
def get_expense_dict():
    with Session(engine) as session:
        expense = session.query(Expense).first()
        return {
            "id": expense.id,
            "description": expense.description,
            "category": expense.category.name
        }
```

### Error 3: Not Handling Exceptions

```python
# ❌ Wrong: Exception leaves transaction open
def add_expense(description, amount, category_id):
    session = Session(engine)
    expense = Expense(description=description, amount=amount, category_id=category_id)
    session.add(expense)
    session.commit()  # What if category_id is invalid?
    # Exception = session left open, consuming resources

# ✅ Right: Cleanup on error
def add_expense(description, amount, category_id):
    with Session(engine) as session:
        try:
            expense = Expense(description=description, amount=amount, category_id=category_id)
            session.add(expense)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
```

## Autoflush Behavior

By default, SQLAlchemy automatically sends pending changes to database before queries:

```python
with Session(engine) as session:
    user = User(name="Alice")
    session.add(user)

    # Autoflush here! User is inserted before query
    all_users = session.query(User).all()
    print(len(all_users))  # Includes Alice
```

**Disable autoflush for precise control**:

```python
with Session(engine) as session:
    session.autoflush = False

    user = User(name="Alice")
    session.add(user)

    all_users = session.query(User).all()
    print(len(all_users))  # Doesn't include Alice (not flushed yet)

    session.flush()  # Now send to database
    all_users = session.query(User).all()
    print(len(all_users))  # Includes Alice
```

## Session Events for Debugging

```python
from sqlalchemy import event
from sqlalchemy.orm import Session

# Log all commits
@event.listens_for(Session, "after_commit")
def receive_after_commit(session):
    print("✅ Transaction committed")

# Log all rollbacks
@event.listens_for(Session, "after_rollback")
def receive_after_rollback(session):
    print("⚠️ Transaction rolled back")

# Log SQL execution
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    print(f"Executing: {statement}")
```

## Best Practices Summary

| Pattern | Use When | Example |
|---------|----------|---------|
| **Context manager** | Simple operations | Reading/writing single object |
| **Try/except** | Operations that can fail | User input validation |
| **Savepoints** | Batch processing | Processing file of expenses |
| **Eager loading** | Relationships needed | Need category with expense |
| **Lazy loading** | Only sometimes needed | Load on demand |
| **Serialization** | Returning data | API responses |

## Real-World Budget Tracker Example

```python
class BudgetManager:
    def __init__(self, engine):
        self.engine = engine

    def add_expense(self, user_id, description, amount, category_name):
        """Add expense with category lookup - atomic operation."""
        with Session(self.engine) as session:
            try:
                # Verify category exists
                category = session.query(Category).filter(
                    Category.name == category_name
                ).first()
                if not category:
                    raise ValueError(f"Category '{category_name}' not found")

                # Create expense
                expense = Expense(
                    user_id=user_id,
                    description=description,
                    amount=amount,
                    category_id=category.id
                )
                session.add(expense)
                session.commit()

                return {"id": expense.id, "status": "created"}
            except Exception as e:
                session.rollback()
                return {"error": str(e), "status": "failed"}

    def get_monthly_summary(self, user_id, year, month):
        """Get spending summary for month."""
        from datetime import date
        with Session(self.engine) as session:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)

            results = session.query(
                Category.name,
                func.sum(Expense.amount).label('total'),
                func.count(Expense.id).label('count')
            ).join(Expense).filter(
                (Expense.user_id == user_id) &
                (Expense.date >= start_date) &
                (Expense.date < end_date)
            ).group_by(Category.name).all()

            return [
                {
                    "category": name,
                    "total": float(total or 0),
                    "count": count
                }
                for name, total, count in results
            ]
```
