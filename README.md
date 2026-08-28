# Nifty Daily Snapshot

A serverless pipeline that pulls the latest closing price and volume for
three NSE-listed stocks and lands them in BigQuery. 
Infrastructure is
managed with Terraform, the pipeline runs as a Cloud Run service that is
triggered on demand.

Stocks covered: RELIANCE, TCS, INFY.


## BigQuery Table schema

- stock_data.daily_prices
  - trade_date  	-	DATE 
  - symbol	        -	STRING 
  - close_price	    -	NUMERIC 
  - volume	        -	INTEGER 
  - fetched_at	    -	TIMESTAMP	


## Setup
 
Requires the gcloud CLI, Terraform, and a GCP project with billing
enabled.
 
```bash
gcloud auth login
gcloud config set project nifty-daily-snapshot
gcloud auth application-default login
```
 
### 1. Create the infrastructure
  
```bash
terraform init
 
terraform apply -var="project_id=nifty-daily-snapshot" \
  -target="google_bigquery_table.daily_prices" \
  -target="google_artifact_registry_repository.images" \
  -target="google_service_account.pipeline"
```
 
### 2. Build and push the image
 
```bash
gcloud services enable cloudbuild.googleapis.com
 
gcloud builds submit \
  --tag asia-south1-docker.pkg.dev/nifty-daily-snapshot/nifty-snapshot/nifty-snapshot:latest
```

 
### 3. Deploy Cloud Run
 
```bash
terraform apply -var="project_id=nifty-daily-snapshot"
```
 
### 4. Trigger the pipeline
 
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  $(terraform output -raw service_url)
```

### 5. End
 
```bash
terraform destroy -var="project_id=nifty-daily-snapshot"
```
 

## What I would do better with more time:
- The table currently holds one snapshot, not history, so I'd extend it to append incrementally.
- Add a scheduler
---

### END

---