"""Keep demo fixture data enabled only during automated tests."""
import os

os.environ.setdefault("MESSWISE_SEED_DEMO_DATA", "true")
