# Execution steps

```
git clone https://github.com/SanthoshRaaj-KR/DemandForecasting-PowerGrid
cd DemandForecasting-PowerGrid
```

### Terminal 1
```
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

### Terminal 2
```
cd frontend 
npm install
npm start
```
