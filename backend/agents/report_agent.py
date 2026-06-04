from agent import generate_health_report


def generate_report(logs: list, report_type: str) -> dict:
    return generate_health_report(logs, report_type)

