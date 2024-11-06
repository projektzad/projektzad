# run.py

from app import create_app

# Create an instance of the Flask app
app = create_app()
# Run the app
if __name__ == '__main__':
    app.run(host="127.0.0.1",port=8080,debug=True)
