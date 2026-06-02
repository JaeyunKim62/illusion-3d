source ~/miniconda3/bin/activate
conda activate rendering

FIRST_IMAGE=img/bird.png
SECOND_IMAGE=img/airplane.png
THIRD_IMAGE=img/tower.png

python train_sdf.py \
  --front ${FIRST_IMAGE} \
  --side ${SECOND_IMAGE} \
  --top ${THIRD_IMAGE} \
  --iters 10000 \
  --hidden 256 \
  --layers 5 \
  --lr 1e-4 \
  --n 30000 \
  --surface-ratio 0.45 \
  --device cuda \
  --retrain \
  --output data/points-windmill-airplane-tower.json


python annotate_sdf_points.py \
  --front ${FIRST_IMAGE} \
  --side ${SECOND_IMAGE} \
  --top ${THIRD_IMAGE} \
  --points data/points-windmill-airplane-tower.json \
  --output data/points-windmill-airplane-tower-sdf.json

python evaluate_projection_metrics.py \
  --front ${FIRST_IMAGE} \
  --side ${SECOND_IMAGE} \
  --top ${THIRD_IMAGE} \
  --points data/points-windmill-airplane-tower-sdf.json \
  --output data/projection-metrics-windmill-airplane-tower.json

python3 -m http.server 8000