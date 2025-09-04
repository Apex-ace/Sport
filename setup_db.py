from app import app, db, seed_games

# This script is meant to be run once to initialize the database.
with app.app_context():
    print("Creating all database tables...")
    db.create_all()
    print("Seeding initial game data...")
    seed_games()
    print("Database setup complete.")
