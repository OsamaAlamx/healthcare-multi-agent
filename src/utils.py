from datetime import time

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SHORT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def format_availability(selected_days: list, start_time: time, end_time: time) -> str:
    """Formats availability into a readable string like 'Mon-Fri | 9:00 AM - 5:00 PM'."""
    if not selected_days:
        return ""

    day_indices = sorted([DAYS_OF_WEEK.index(d) for d in selected_days])

    ranges = []
    start = prev = day_indices[0]
    for i in range(1, len(day_indices)):
        if day_indices[i] == prev + 1:
            prev = day_indices[i]
        else:
            ranges.append((start, prev))
            start = prev = day_indices[i]
    ranges.append((start, prev))

    parts = [
        SHORT_DAYS[s] if s == e else f"{SHORT_DAYS[s]}-{SHORT_DAYS[e]}"
        for s, e in ranges
    ]
    time_str = (
        f"{start_time.strftime('%I:%M %p').lstrip('0')} - "
        f"{end_time.strftime('%I:%M %p').lstrip('0')}"
    )
    return f"{', '.join(parts)} | {time_str}"