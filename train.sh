source ~/miniconda3/bin/activate
conda activate render

# pip install -r requirements.txt

FIRST_IMAGE=img/bird.png
SECOND_IMAGE=img/airplane.png
THIRD_IMAGE=img/tower.png

python train_sdf.py \
  --front ${FIRST_IMAGE} \
  --side ${SECOND_IMAGE} \
  --top ${THIRD_IMAGE} \
  --iters 5000 \
  --hidden 256 \
  --layers 5 \
  --lr 1e-4 \
  --n 30000 \
  --surface-ratio 0.45 \
  --device cuda \
  --metrics-output data/training-metrics.jsonl \
  --metrics-interval 500 \
  --metrics-samples 30000 \
  --retrain \
  --output data/points.json


python annotate_sdf_points.py \
  --front ${FIRST_IMAGE} \
  --side ${SECOND_IMAGE} \
  --top ${THIRD_IMAGE} \
  --points data/points.json \
  --output data/points-sdf-annotated.json

python evaluate_projection_metrics.py \
  --front ${FIRST_IMAGE} \
  --side ${SECOND_IMAGE} \
  --top ${THIRD_IMAGE} \
  --points data/points-sdf-annotated.json \
  --output data/projection-metrics-sdf.json

python3 -m http.server 8000