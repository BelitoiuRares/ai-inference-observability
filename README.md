# Observability pentru un Endpoint AI de Inferenta

Acest proiect adauga un stack de observabilitate peste un endpoint AI de inferenta rulat local cu Ollama si expus prin NGINX.

Totul ruleaza local, CPU-only, fara servicii cloud.

Stack-ul include:

- Ollama pentru rularea modelelor AI
- NGINX ca reverse proxy
- un exporter propriu pentru metrici
- Prometheus pentru colectarea metricilor
- Grafana pentru dashboard si alertare

Proiectul este reproductibil: dupa clonarea repository-ului, totul porneste cu o singura comanda:

docker compose up -d

---

## 1. Arhitectura

Client
  |
  v
NGINX :8080
  |
  v
AI Exporter :8000
  |
  v
Ollama :11434
  |
  v
Modele:
- qwen2:0.5b
- tinyllama

Prometheus :9090 scrape-uieste AI Exporter /metrics
Grafana :3000 citeste datele din Prometheus

Fluxul principal este:

Request utilizator -> NGINX -> AI Exporter -> Ollama -> raspuns model

Exporter-ul este pus intre NGINX si Ollama pentru a putea masura requesturile si pentru a extrage metrici specifice din raspunsurile Ollama.

---

## 2. Cerinte

Pentru rulare ai nevoie de:

- Docker
- Docker Compose plugin
- o masina locala sau o masina virtuala Linux

Proiectul a fost testat pe Ubuntu 24.04, CPU-only.

Nu sunt necesare servicii cloud.

---

## 3. Pornire proiect

##3.1  ## Instalare Docker pe Ubuntu 24.04

Pe o masina virtuala curata cu Ubuntu 24.04, Docker poate fi instalat cu urmatoarele comenzi:

apt update
apt install -y ca-certificates curl gnupg

install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
gpg --dearmor -o /etc/apt/keyrings/docker.gpg

chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

Dupa instalare, se verifica Docker cu:

docker --version
docker compose version
docker run hello-world

Daca apare mesajul "Hello from Docker!", instalarea Docker este functionala.

##facem download de pe link-ul public dockerul cu fisierele noastre
apt install -y git curl jq

cd ~
git clone https://github.com/BelitoiuRares/ai-inference-observability.git
cd ai-inference-observability

docker compose up -d



##3.2
Din folderul proiectului, ruleaza:

docker compose up -d

Prima pornire poate dura mai mult, deoarece se descarca imaginile Docker si modelele Ollama:

Personal, prima pornire la modelul qwen2:0.5b a durat intre 2-3 minute iar dupa ce am descarcat si tinyllama undeva intre 3-6 minute prima pornire.

- qwen2:0.5b
- tinyllama

Containerul `model-init` descarca modelele si apoi se opreste. Este normal ca acesta sa apara ca `Exited (0)` dupa ce termina.

Verifica serviciile:

docker compose ps

Serviciile principale trebuie sa fie `Up`:

ollama
ai-exporter
nginx
prometheus
grafana
root@rares-VMware-Virtual-Platform:~/ai-observability-project# docker compose ps
NAME          IMAGE                                  COMMAND                  SERVICE       CREATED          STATUS                    PORTS
ai-exporter   ai-observability-project-ai-exporter   "uvicorn main:app --…"   ai-exporter   40 minutes ago   Up 40 minutes             0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
grafana       grafana/grafana:11.4.0                 "/run.sh"                grafana       55 minutes ago   Up 47 minutes             0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
nginx         nginx:1.27-alpine                      "/docker-entrypoint.…"   nginx         55 minutes ago   Up 55 minutes             80/tcp, 0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp
ollama        ollama/ollama:latest                   "/bin/ollama serve"      ollama        55 minutes ago   Up 55 minutes (healthy)   11434/tcp
prometheus    prom/prometheus:v3.1.0                 "/bin/prometheus --c…"   prometheus    55 minutes ago   Up 55 minutes             0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp

---

## 4. Servicii si porturi

SERVICE       STATE     <no value>
ai-exporter   running   [{0.0.0.0 8000 8000 tcp} {:: 8000 8000 tcp}]
grafana       running   [{0.0.0.0 3000 3000 tcp} {:: 3000 3000 tcp}]
nginx         running   [{ 80 0 tcp} {0.0.0.0 8080 8080 tcp} {:: 8080 8080 tcp}]
ollama        running   [{ 11434 0 tcp}]
prometheus    running   [{0.0.0.0 9090 9090 tcp} {:: 9090 9090 tcp}]
---

## 5. Testare endpoint AI

Endpoint-ul public este:

http://localhost:8080/api/generate

Test pentru modelul `qwen2:0.5b`:

curl -s http://localhost:8080/api/generate -d '{
  "model": "qwen2:0.5b",
  "prompt": "Spune-mi un fapt scurt.",
  "stream": false
}' | jq

Test pentru modelul `tinyllama`:

curl -s http://localhost:8080/api/generate -d '{
  "model": "tinyllama",
  "prompt": "Spune-mi un fapt scurt.",
  "stream": false
}' | jq

Daca totul functioneaza, comanda va intoarce un raspuns JSON generat de Ollama.
Acest proces va dura undeva intre 3-6 minute, depinde de masina.
---

## 6. Metrici expuse

Metricile sunt expuse de AI Exporter la:

http://localhost:8000/metrics

Verificare rapida:

curl -s http://localhost:8000/metrics | grep -E "ai_requests_total|ai_request_duration_seconds_count|ollama_tokens_per_second"

Metricile principale sunt:

Metrica | Tip | Explicatie

 `ai_requests_total` | Counter | Numarul total de requesturi, grupate dupa metoda, path si clasa de status |
 `ai_errors_total` | Counter | Numarul total de erori |
 `ai_request_duration_seconds` | Histogram | Latenta requesturilor catre endpoint-ul AI |
 `ollama_total_duration_seconds` | Histogram | Durata totala raportata de Ollama pentru inferenta |
 `ollama_tokens_per_second` | Gauge | Tokens/secunda calculati din `eval_count` si `eval_duration` |
 `ollama_eval_tokens_total` | Counter | Numarul total de tokens generati |

---

## 7. De ce au fost alese aceste metrici

Metricile au fost alese ca sa raspunda la intrebarile importante pentru un endpoint de inferenta:

- cate requesturi primeste endpoint-ul;
- cat de rapid raspunde;
- care este latenta mediana, p50;
- care este latenta p95, utila pentru SLA;
- daca apar erori 4xx sau 5xx;
- cati tokens pe secunda genereaza modelul;
- cum difera latenta intre doua modele.

Pentru latenta se folosesc histograme Prometheus, deoarece permit calculul procentelor cu `histogram_quantile`.

Pentru metricile specifice AI, exporter-ul citeste din raspunsul Ollama campurile:

- `total_duration`
- `eval_count`
- `eval_duration`

Formula folosita pentru tokens/secunda este:

tokens/secunda = eval_count / (eval_duration in secunde)

---

## 8. Prometheus

Prometheus este disponibil la:

http://localhost:9090

Target-ul configurat este:

ai-exporter:8000

Verificare din interfata Prometheus:

Status -> Target health

Target-ul trebuie sa fie `UP`.

Verificare din terminal:

curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, scrapeUrl: .scrapeUrl, health: .health, lastError: .lastError}'

{
  "job": "ai-exporter",
  "scrapeUrl": "http://ai-exporter:8000/metrics",
  "health": "up",
  "lastError": ""
}

Rezultat asteptat:

job: ai-exporter
health: up
lastError: ""

---

## 9. Query-uri Prometheus utile

Request rate:

sum(rate(ai_requests_total{path="/api/generate"}[5m]))

Latenta p50:

histogram_quantile(
  0.50,
  sum(rate(ai_request_duration_seconds_bucket{path="/api/generate"}[5m])) by (le)
)

Latenta p95:

histogram_quantile(
  0.95,
  sum(rate(ai_request_duration_seconds_bucket{path="/api/generate"}[5m])) by (le)
)

Rata erori 4xx:

sum(rate(ai_requests_total{path="/api/generate",status_class="4xx"}[5m])) or vector(0)

Rata erori 5xx:

sum(rate(ai_requests_total{path="/api/generate",status_class="5xx"}[5m])) or vector(0)

Tokens/secunda:

ollama_tokens_per_second

Comparatie latenta p95 intre modele:

histogram_quantile(
  0.95,
  sum(rate(ollama_total_duration_seconds_bucket[15m])) by (model, le)
)

---

## 10. Grafana

Grafana este disponibila la:

http://localhost:3000

Login implicit:

user:admin
pass:admin

Dashboard-ul se gaseste in Grafana la:

Dashboards -> AI Observability -> AI Inference Observability

Dashboard-ul include:

- Request Rate
- Latency p50
- Latency p95
- Request Rate by Status Class
- 4xx Error Rate
- 5xx Error Rate
- Tokens Per Second
- Latency Trend
- Model Latency p95 Comparison

---

## 11. Provisioning Grafana

Grafana este configurata din fisiere, nu manual din interfata.

Datasource-ul Prometheus este definit in:

grafana/provisioning/datasources/prometheus.yml

Dashboard-ul este definit in:

grafana/dashboards/ai-observability-dashboard.json

Provider-ul pentru dashboard-uri este definit in:

grafana/provisioning/dashboards/dashboards.yml

Regula de alertare este definita in:

grafana/provisioning/alerting/alert-rules.yml

Acest lucru face ca datasource-ul, dashboard-ul si alerta sa apara automat dupa `docker compose up -d`.

---

## 12. Generare trafic pentru dashboard

Pentru a popula dashboard-ul cu date reale, ruleaza:

for i in {1..20}; do
  curl -s http://localhost:8080/api/generate -d '{
    "model": "qwen2:0.5b",
    "prompt": "Spune-mi un fapt scurt.",
    "stream": false
  }' > /dev/null
  sleep 1
done

Pentru comparatia intre cele doua modele:

for i in {1..10}; do
  curl -s http://localhost:8080/api/generate -d '{
    "model": "qwen2:0.5b",
    "prompt": "Spune-mi un fapt scurt.",
    "stream": false
  }' > /dev/null

  curl -s http://localhost:8080/api/generate -d '{
    "model": "tinyllama",
    "prompt": "Spune-mi un fapt scurt.",
    "stream": false
  }' > /dev/null

  sleep 1
done

Dupa rulare, dashboard-ul trebuie sa afiseze date pentru ambele modele.

---

## 13. Alertare SLA

Alerta configurata este:

AI High Latency p95

Conditia de alertare este:

p95 latency > 2 secunde timp de 1 minut

Regula este evaluata la fiecare 10 secunde.

Query-ul folosit este:

histogram_quantile(
  0.95,
  sum(rate(ai_request_duration_seconds_bucket{path="/api/generate"}[1m])) by (le)
)

Alerta poate fi verificata in Grafana la:

Alerting -> Alert rules -> AI High Latency p95

Starile posibile sunt:

Normal -> Pending -> Firing

---

## 14. Cum se declanseaza manual alerta

Ruleaza requesturi repetate catre endpoint:

for i in {1..60}; do
  curl -s http://localhost:8080/api/generate -d '{
    "model": "qwen2:0.5b",
    "prompt": "Scrie un paragraf scurt despre observabilitate, monitorizare, latenta si performanta sistemelor AI.",
    "stream": false
  }' > /dev/null
  sleep 1
done

Apoi verifica in Grafana:

Alerting -> Alert rules

Daca p95 ramane peste 2 secunde timp de 1 minut, alerta va intra in `Firing`.


grafana/provisioning/alerting/alert-rules.yml

Bonus: se poate configura serviciul SMTP pentru ca alerta sa ajunga pe un mail designat la administrator

---

## 15. Oprire proiect

Pentru oprire:

docker compose down

Aceasta comanda opreste containerele, dar pastreaza volumele Docker.


docker compose down -v

Optiunea `-v` sterge volumele, inclusiv modelele descarcate si datele locale Prometheus/Grafana.

---

## 16. Decizii si compromisuri

A fost folosit un exporter propriu deoarece permite masurarea requesturilor si extragerea metricilor specifice Ollama din raspunsul JSON.

A fost pastrat un singur serviciu Ollama, in care sunt disponibile doua modele:

- `qwen2:0.5b`
- `tinyllama`


Comparatia de latenta intre modele este facuta cu metrica:

ollama_total_duration_seconds

Modelul `qwen2:0.5b` este mic si rapid. `tinyllama` poate avea latenta mai mare pe CPU, mai ales daca genereaza raspunsuri lungi.

Primul request dupa restart poate fi mai lent, deoarece Ollama incarca modelul in memorie.

---

## 17. Structura repository-ului

├── docker-compose.yml
├── exporter
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── .gitignore
├── grafana
│   ├── dashboards
│   │   └── ai-observability-dashboard.json
│   └── provisioning
│       ├── alerting
│       │   └── alert-rules.yml
│       ├── dashboards
│       │   └── dashboards.yml
│       └── datasources
│           └── prometheus.yml
├── nginx
│   └── nginx.conf
├── prometheus
│   └── prometheus.yml
├── README_RARES.md
└── .README_RARES.md.swp

10 directories, 13 files
---

## 18. Reproductibilitate si siguranta

Tot ce este necesar pentru rulare este inclus in repository:

- `docker-compose.yml`
- configuratia NGINX
- codul exporter-ului
- configuratia Prometheus
- provisioning Grafana pentru datasource
- provisioning Grafana pentru dashboard
- provisioning Grafana pentru alerta
- README cu pasii de rulare si testare
