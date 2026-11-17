from flask import Flask
app = Flask(__name__)


@app.route('/')
def hello_world():
    return '<h2>Hello, World! From SCK: 172.19.129.254</h2>'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
