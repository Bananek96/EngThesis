from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route('/', methods=['GET'])
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        print(str(e))  # Log the exception
        return "Internal Server Error", 500


@app.route('/pl', methods=['GET'])
def index_pl():
    try:
        return render_template('index_pl.html')
    except Exception as e:
        print(str(e))  # Log the exception
        return "Internal Server Error", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
