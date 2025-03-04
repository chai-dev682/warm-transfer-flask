from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from flask_migrate import upgrade as upgrade_database
from warm_transfer_flask import app, db, prepare_app
import uvicorn
from warm_transfer_flask.fastapi_app import app as fastapi_app

prepare_app()
migrate = Migrate(app, db)

manager = Manager(app)
manager.add_command('db', MigrateCommand)

@manager.command 
def runserver():
    """Run the server with FastAPI"""
    uvicorn.run(fastapi_app, host="0.0.0.0", port=5000)


@manager.command
def test():
    """Run the unit tests."""
    import sys
    import unittest

    prepare_app(environment='testing')
    upgrade_database()
    tests = unittest.TestLoader().discover('.', pattern="*_tests.py")
    test_result = unittest.TextTestRunner(verbosity=2).run(tests)

    if not test_result.wasSuccessful():
        sys.exit(1)


@manager.command
def dbseed():
    pass


if __name__ == "__main__":
    manager.run()
