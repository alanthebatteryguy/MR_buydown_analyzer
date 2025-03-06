from sqlalchemy import create_engine, inspect

def get_database_context():
    engine = create_engine('sqlite:///mbs_data.db')
    inspector = inspect(engine)
    
    context = {
        "tables": {},
        "examples": [
            "Show me current 30-year mortgage rates",
            "Compare ROI for 5% and 5.5% coupons",
            "Plot price trends for 6% MBS"
        ]
    }
    
    for table in inspector.get_table_names():
        context["tables"][table] = [
            str(col['name']) for col in inspector.get_columns(table)
        ]
    
    return context