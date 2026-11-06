"""The assessment's billing rule, shared by matching and approved writes."""


def financial_protected(account_record):
    """Both revenue history and unpaid AR require the CHOW workflow."""
    return (
        float(account_record["lifetime_revenue"]) > 0
        and float(account_record["outstanding_ar"]) > 0
    )
