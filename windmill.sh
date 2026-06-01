source ~/miniconda3/bin/activate
conda activate rendering

python train_sdf.py \
  --front img_candidates/design_windmill.png \
  --side img/airplane.png \
  --top img/Tower.png \
  --iters 5000 \
  --hidden 256 \
  --layers 3 \
  --lr 1e-4 \
  --n 30000 \
  --surface-ratio 0.45 \
  --device cuda \
  --retrain \
  --output data/points-windmill-airplane-tower.json


python annotate_sdf_points.py \
  --front img_candidates/design_windmill.png \
  --side img/airplane.png \
  --top img/Tower.png \
  --points data/points-windmill-airplane-tower.json \
  --output data/points-windmill-airplane-tower-sdf.json

python eval/evaluate_projection_metrics.py \
  --front img_candidates/design_windmill.png \
  --side img/airplane.png \
  --top img/Tower.png \
  --points data/points-windmill-airplane-tower-sdf.json \
  --output data/projection-metrics-windmill-airplane-tower.json

python3 -m http.server 8000