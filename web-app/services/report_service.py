from datetime import datetime, timedelta
from config import Config
from database import get_db

def calculate_revenue(report_type="All Time"):
    """
    Calculates total revenue for a given period from checked-out stays.
    Exact calculation formula from desktop calculate_revenue().
    """
    now = datetime.now()
    if report_type == 'Daily':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif report_type == 'Weekly':
        start_of_week = now - timedelta(days=now.weekday())
        start_date = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    elif report_type == 'Monthly':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # 'All Time'
        start_date = datetime.min

    db = get_db()
    cur = db.execute("""
        SELECT days, food_plan, checkout_datetime, total_amount
        FROM bookings
        WHERE status = 'Checked Out'
    """)
    rows = cur.fetchall()

    total_revenue = 0.0

    for b in rows:
        try:
            checkout_dt_str = b['checkout_datetime']
            if not checkout_dt_str:
                continue

            checkout_dt = datetime.strptime(checkout_dt_str, "%d-%m-%Y %I:%M %p")

            if report_type == 'All Time' or checkout_dt >= start_date:
                # If pre-calculated in DB, use it; otherwise compute dynamically
                if b['total_amount'] is not None and b['total_amount'] > 0:
                    total_revenue += float(b['total_amount'])
                else:
                    days = max(1, int(b['days']))
                    food_plan = b['food_plan']
                    room_charge = Config.ROOM_RATE * days
                    food_charge = Config.FOOD_PRICES.get(food_plan, 0) * days
                    subtotal = room_charge + food_charge
                    total_revenue += subtotal * (1 + Config.GST_RATE)
        except Exception:
            continue

    return total_revenue

def get_complete_revenue_report(selected_type="Monthly"):
    """Returns all period comparisons and formatted breakdown."""
    daily_rev = calculate_revenue("Daily")
    weekly_rev = calculate_revenue("Weekly")
    monthly_rev = calculate_revenue("Monthly")
    all_time_rev = calculate_revenue("All Time")

    selected_type = selected_type if selected_type in ("Daily", "Weekly", "Monthly", "All Time") else "Monthly"
    selected_rev = {
        "Daily": daily_rev,
        "Weekly": weekly_rev,
        "Monthly": monthly_rev,
        "All Time": all_time_rev
    }[selected_type]

    report_text = f"              --- Hotel Revenue Report ---\n\n"
    report_text += f"{'      Total Revenue (Daily):':<30} ₹{daily_rev:>18,.2f}\n"
    report_text += f"{'      Total Revenue (Weekly):':<30} ₹{weekly_rev:>18,.2f}\n"
    report_text += f"{'      Total Revenue (Monthly):':<30} ₹{monthly_rev:>18,.2f}\n"
    report_text += f"{'      Total Revenue (All Time):':<30} ₹{all_time_rev:>18,.2f}\n"
    report_text += "\n"
    report_text += f"      --------------------------------------------------\n"
    report_text += f"{f'      SELECTED REPORT ({selected_type.upper()}):':<30} ₹{selected_rev:>18,.2f}\n"

    return {
        "success": True,
        "selected_type": selected_type,
        "summary": {
            "daily": daily_rev,
            "weekly": weekly_rev,
            "monthly": monthly_rev,
            "all_time": all_time_rev,
            "selected": selected_rev,
            "total_revenue": selected_rev
        },
        "formatted": {
            "daily": f"₹{daily_rev:,.2f}",
            "weekly": f"₹{weekly_rev:,.2f}",
            "monthly": f"₹{monthly_rev:,.2f}",
            "all_time": f"₹{all_time_rev:,.2f}",
            "selected": f"₹{selected_rev:,.2f}",
            "report_text": report_text
        },
        "report_text": report_text,
        "total_revenue": selected_rev
    }
