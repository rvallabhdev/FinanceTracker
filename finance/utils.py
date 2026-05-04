DEFAULT_CATEGORIES = [
    ("Salary", "Income"),
    ("Freelance Income", "Income"),
    ("Other Income", "Income"),

    ("Food & Dining", "Expense"),
    ("Rent / Housing", "Expense"),
    ("Transport", "Expense"),
    ("Utilities", "Expense"),
    ("Shopping", "Expense"),
    ("Health", "Expense"),
    ("Entertainment", "Expense"),
    ("Education", "Expense"),
    ("Miscellaneous", "Expense"),
]


def create_default_categories(user):
    from .models import Category

    for name, cat_type in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(
            user=user,
            name=name,
            category_type=cat_type,
            defaults={"is_default": True}
        )