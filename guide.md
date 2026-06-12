### run app

```ps1
docker compose up --build -d
```

visit `http://localhost:8000/`

### stop app

```ps1
docker compose down
```

### ppt compile

```ps1
docker build -t iot-deck ./deck
docker run --rm -v "${PWD}/deck:/out" iot-deck
```