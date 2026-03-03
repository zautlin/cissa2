"""
Complete Budget Tracker Application using SQLAlchemy ORM and Neon PostgreSQL

This is a fully working example that demonstrates:
- Model definitions (User, Category, Expense)
- Database initialization
- CRUD operations
- Transactions and error handling
- Queries with relationships
- Connection to Neon
"""

import os
from datetime import datetime, date
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Date,
    ForeignKey,
    func,
    event,
)
from sqlalchemy.orm import declarative_base, relationship, Session
from sqlalchemy.pool import QueuePool

# Load environment variables
load_dotenv()

# ============================================================================
# DATABASE SETUP
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env file")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,           # Keep 5 connections open
    max_overflow=10,       # Allow 10 more if needed
    pool_recycle=3600,     # Recycle connections after 1 hour
    pool_pre_ping=True,    # Test connection before use
    echo=False             # Set to True for SQL debugging
)

Base = declarative_base()


# ============================================================================
# MODELS
# ============================================================================

class User(Base):
    """User account for budget tracking."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    expenses = relationship("Expense", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', name='{self.name}')>"


class Category(Base):
    """Budget categories (Food, Transportation, Entertainment, etc.)."""
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(7), default="#FF6B6B")  # Hex color code

    # Relationships
    expenses = relationship("Expense", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Category(name='{self.name}')>"


class Expense(Base):
    """Individual expense entry."""
    __tablename__ = 'expenses'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    description = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, default=date.today)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="expenses")
    category = relationship("Category", back_populates="expenses")

    def __repr__(self):
        return f"<Expense(id={self.id}, description='{self.description}', amount=${self.amount:.2f})>"


# ============================================================================
# INITIALIZATION
# ============================================================================

def init_database():
    """Create all tables in database."""
    Base.metadata.create_all(engine)
    print("✅ Database initialized")


def seed_data():
    """Add sample data for testing."""
    with Session(engine) as session:
        # Check if data already exists
        if session.query(User).count() > 0:
            print("⚠️ Database already has data, skipping seed")
            return

        # Create user
        user = User(email="alice@example.com", name="Alice Smith")
        session.add(user)

        # Create categories
        categories = [
            Category(name="Food", color="#FF6B6B"),
            Category(name="Transportation", color="#4ECDC4"),
            Category(name="Entertainment", color="#95E1D3"),
            Category(name="Utilities", color="#F38181"),
        ]
        session.add_all(categories)
        session.flush()  # Populate IDs

        # Create expenses
        expenses = [
            Expense(
                user_id=user.id,
                category_id=categories[0].id,
                description="Groceries at Trader Joe's",
                amount=52.50,
                date=date(2024, 1, 15)
            ),
            Expense(
                user_id=user.id,
                category_id=categories[0].id,
                description="Lunch at Restaurant",
                amount=18.75,
                date=date(2024, 1, 16)
            ),
            Expense(
                user_id=user.id,
                category_id=categories[1].id,
                description="Gas",
                amount=45.00,
                date=date(2024, 1, 17)
            ),
            Expense(
                user_id=user.id,
                category_id=categories[2].id,
                description="Movie tickets",
                amount=30.00,
                date=date(2024, 1, 18)
            ),
        ]
        session.add_all(expenses)
        session.commit()
        print("✅ Sample data added")


# ============================================================================
# CRUD OPERATIONS
# ============================================================================

def create_expense(user_id, description, amount, category_id, expense_date=None):
    """Create a new expense."""
    try:
        with Session(engine) as session:
            expense = Expense(
                user_id=user_id,
                description=description,
                amount=amount,
                category_id=category_id,
                date=expense_date or date.today()
            )
            session.add(expense)
            session.commit()
            return {"success": True, "id": expense.id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_expenses(user_id, category_id=None):
    """Get expenses for a user, optionally filtered by category."""
    with Session(engine) as session:
        query = session.query(Expense).filter(Expense.user_id == user_id)
        if category_id:
            query = query.filter(Expense.category_id == category_id)
        return query.order_by(Expense.date.desc()).all()


def update_expense(expense_id, **kwargs):
    """Update an expense. Allowed kwargs: description, amount, category_id, date."""
    allowed_fields = {'description', 'amount', 'category_id', 'date'}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    try:
        with Session(engine) as session:
            expense = session.query(Expense).filter(Expense.id == expense_id).first()
            if not expense:
                return {"success": False, "error": "Expense not found"}

            for field, value in updates.items():
                setattr(expense, field, value)

            session.commit()
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_expense(expense_id):
    """Delete an expense."""
    try:
        with Session(engine) as session:
            expense = session.query(Expense).filter(Expense.id == expense_id).first()
            if not expense:
                return {"success": False, "error": "Expense not found"}

            session.delete(expense)
            session.commit()
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# QUERIES WITH RELATIONSHIPS
# ============================================================================

def get_monthly_summary(user_id, year, month):
    """Get spending summary grouped by category for a specific month."""
    with Session(engine) as session:
        # Calculate date range
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        current_month = date(year, month, 1)

        # Query: sum amount by category
        results = session.query(
            Category.name,
            func.sum(Expense.amount).label('total'),
            func.count(Expense.id).label('count')
        ).join(Expense).filter(
            (Expense.user_id == user_id) &
            (Expense.date >= current_month) &
            (Expense.date < next_month)
        ).group_by(Category.name).all()

        return [
            {
                "category": name,
                "total": float(total or 0),
                "count": count
            }
            for name, total, count in results
        ]


def get_expenses_by_category(user_id):
    """Get all expenses grouped by category."""
    with Session(engine) as session:
        categories = session.query(Category).all()

        result = {}
        for category in categories:
            expenses = session.query(Expense).filter(
                (Expense.user_id == user_id) &
                (Expense.category_id == category.id)
            ).all()

            result[category.name] = {
                "count": len(expenses),
                "total": sum(e.amount for e in expenses),
                "expenses": [
                    {
                        "id": e.id,
                        "description": e.description,
                        "amount": e.amount,
                        "date": e.date.isoformat()
                    }
                    for e in expenses
                ]
            }

        return result


def get_top_expenses(user_id, limit=10):
    """Get the highest-value expenses."""
    with Session(engine) as session:
        return session.query(Expense).filter(
            Expense.user_id == user_id
        ).order_by(Expense.amount.desc()).limit(limit).all()


def get_spending_trend(user_id, months=6):
    """Get total spending per month for the last N months."""
    with Session(engine) as session:
        results = session.query(
            func.date_trunc('month', Expense.date).label('month'),
            func.sum(Expense.amount).label('total')
        ).filter(
            Expense.user_id == user_id
        ).group_by(
            func.date_trunc('month', Expense.date)
        ).order_by(
            func.date_trunc('month', Expense.date).desc()
        ).limit(months).all()

        return [
            {
                "month": month.isoformat() if month else None,
                "total": float(total or 0)
            }
            for month, total in results
        ]


# ============================================================================
# TRANSACTION EXAMPLES
# ============================================================================

def transfer_budget(user_id, from_category_id, to_category_id, amount):
    """
    Atomic operation: Subtract from one category, add to another.
    All or nothing - if any fails, both roll back.
    """
    try:
        with Session(engine) as session:
            from_cat = session.query(Category).filter(
                Category.id == from_category_id
            ).first()
            to_cat = session.query(Category).filter(
                Category.id == to_category_id
            ).first()

            if not from_cat or not to_cat:
                raise ValueError("Category not found")

            # Create both transactions atomically
            from_expense = Expense(
                user_id=user_id,
                category_id=from_category_id,
                description=f"Transfer to {to_cat.name}",
                amount=-amount
            )
            to_expense = Expense(
                user_id=user_id,
                category_id=to_category_id,
                description=f"Transfer from {from_cat.name}",
                amount=amount
            )

            session.add(from_expense)
            session.add(to_expense)
            session.commit()  # Both succeed or both fail

            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_user_expenses(user_id):
    """Pretty-print all expenses for a user."""
    with Session(engine) as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"User {user_id} not found")
            return

        print(f"\n📊 Expenses for {user.name} ({user.email})")
        print("-" * 70)

        expenses = session.query(Expense).filter(
            Expense.user_id == user_id
        ).order_by(Expense.date.desc()).all()

        for expense in expenses:
            print(f"  {expense.date}  | {expense.category.name:15} | ${expense.amount:8.2f} | {expense.description}")

        total = sum(e.amount for e in expenses)
        print("-" * 70)
        print(f"Total: ${total:.2f}\n")


def test_connection():
    """Test database connection."""
    try:
        with Session(engine) as session:
            result = session.execute("SELECT 1")
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Initialize database
    init_database()

    # Test connection
    if not test_connection():
        exit(1)

    # Seed sample data (optional - comment out if you want fresh data)
    seed_data()

    # Example usage
    user_id = 1

    # Create new expense
    print("\n➕ Creating new expense...")
    result = create_expense(
        user_id=user_id,
        description="Dinner at restaurant",
        amount=45.75,
        category_id=1
    )
    print(f"  Result: {result}")

    # Print all expenses
    print_user_expenses(user_id)

    # Get monthly summary
    print("\n📈 Monthly Summary (January 2024):")
    summary = get_monthly_summary(user_id, 2024, 1)
    for item in summary:
        print(f"  {item['category']:20} | Count: {item['count']:2} | Total: ${item['total']:8.2f}")

    # Get category breakdown
    print("\n🏷️ Expenses by Category:")
    by_category = get_expenses_by_category(user_id)
    for category, data in by_category.items():
        if data['count'] > 0:
            print(f"  {category:20} | Count: {data['count']:2} | Total: ${data['total']:8.2f}")

    # Get top expenses
    print("\n🔝 Top 5 Expenses:")
    top = get_top_expenses(user_id, 5)
    for expense in top:
        print(f"  ${expense.amount:8.2f} | {expense.category.name:15} | {expense.description}")

    print("\n✅ All operations completed successfully!")
