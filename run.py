import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Render provides the port
    app.run(host='0.0.0.0', port=port, debug=True)

wsgi_app = app