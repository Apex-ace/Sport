#!/usr/bin/env python3
"""
Simple seed script to check and populate games data
"""
import os
import sys
from dotenv import load_dotenv, find_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv(find_dotenv(), override=True)

try:
    from app import app, db, Game
    print("Successfully imported Flask app components")
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def check_and_seed():
    """Check database and seed if needed"""
    try:
        with app.app_context():
            print("Creating tables...")
            db.create_all()
            
            print("Checking games table...")
            games_count = Game.query.count()
            print(f"Current games count: {games_count}")
            
            if games_count == 0:
                print("Adding games...")
                games_data = [
                    {"name": "Basketball", "max_players": 10, "duration_minutes": 60},
                    {"name": "Football", "max_players": 22, "duration_minutes": 90},
                    {"name": "Tennis", "max_players": 4, "duration_minutes": 90},
                    {"name": "Badminton", "max_players": 4, "duration_minutes": 60},
                    {"name": "Table Tennis", "max_players": 4, "duration_minutes": 30},
                    {"name": "Volleyball", "max_players": 12, "duration_minutes": 60},
                    {"name": "Cricket", "max_players": 22, "duration_minutes": 180},
                    {"name": "Swimming", "max_players": 8, "duration_minutes": 45},
                ]
                
                for game_data in games_data:
                    game = Game(**game_data)
                    db.session.add(game)
                
                db.session.commit()
                print(f"Added {len(games_data)} games successfully!")
            else:
                print("Games already exist, skipping seed.")
                
    except Exception as e:
        print(f"Database error: {e}")
        print("This might be a connection issue or missing .env configuration")

if __name__ == "__main__":
    check_and_seed()
