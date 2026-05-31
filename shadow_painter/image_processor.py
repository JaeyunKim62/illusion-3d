import cv2
import numpy as np
from scipy.spatial import Voronoi

def load_and_preprocess_image(filepath, target_size=(512, 512)):
    """
    Loads an image from filepath and resizes it to target_size (maintaining aspect ratio).
    Returns the RGB image, grayscale image, and aspect ratio (W/H).
    """
    # Read image
    img = cv2.imread(filepath)
    if img is None:
        raise FileNotFoundError(f"Could not read image from {filepath}")
    
    # Convert BGR to RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Resize keeping aspect ratio
    h, w = img_rgb.shape[:2]
    aspect = w / h
    
    if w > h:
        new_w = target_size[0]
        new_h = int(new_w / aspect)
    else:
        new_h = target_size[1]
        new_w = int(new_h * aspect)
        
    img_rgb = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    
    return img_rgb, img_gray, aspect

def generate_mask(img_gray, mode='full'):
    """
    Generates a binary mask of the target area.
    - 'full': returns a mask of all 255s (entire canvas).
    - 'silhouette': uses Otsu's thresholding to isolate foreground objects.
    """
    h, w = img_gray.shape
    if mode == 'full':
        return np.ones((h, w), dtype=np.uint8) * 255
    
    # Mode: 'silhouette'
    # Use Otsu's thresholding
    _, mask = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Heuristic: Check if background is actually light or dark
    # We inspect the border pixels of the image
    border_pixels = np.concatenate([
        img_gray[0, :],          # Top row
        img_gray[-1, :],         # Bottom row
        img_gray[:, 0],          # Left col
        img_gray[:, -1]          # Right col
    ])
    mean_border = np.mean(border_pixels)
    
    # If the border is dark (mean_border < 127), then the background is dark.
    # Thresh binary inv was used assuming light background. If dark background, we invert it back.
    if mean_border < 127:
        mask = cv2.bitwise_not(mask)
        
    # Apply morphological opening to clean up noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    return mask

def generate_voronoi_pieces(img_rgb, mask, num_pieces, jitter_factor=0.5, min_piece_pixels=15):
    """
    Segments the masked area of img_rgb into high-quality superpixel pieces using direct 5D K-Means
    label mapping and contour detection in CIELAB space. This preserves exact shape boundaries,
    fine color limits, and prevents geometric/convex hull distortions.
    
    Returns a list of dicts, each representing a piece:
    {
        'centroid': (cx, cy),       # 2D centroid of the piece
        'vertices': np.ndarray,      # N x 2 vertices relative to centroid (polygon)
        'color': (r, g, b),         # Normalized RGB color [0.0, 1.0]
        'pixel_count': int          # Area of the piece in pixels
    }
    """
    h, w = mask.shape
    
    # Extract coordinates of pixels inside the mask
    coords = np.argwhere(mask > 0)
    
    if len(coords) < 10:
        # Fallback to a uniform grid if mask is empty or too small
        aspect = w / h
        cols = int(np.sqrt(num_pieces * aspect))
        cols = max(cols, 2)
        rows = int(np.ceil(num_pieces / cols))
        rows = max(rows, 2)
        xs = np.linspace(0, w, cols + 2)[1:-1]
        ys = np.linspace(0, h, rows + 2)[1:-1]
        
        pieces = []
        # Create small uniform rectangular pieces
        dx = w / (cols + 1)
        dy = h / (rows + 1)
        half_dx = dx * 0.45
        half_dy = dy * 0.45
        
        for y in ys:
            for x in xs:
                centroid = (x, y)
                vertices_local = np.array([
                    [-half_dx, -half_dy],
                    [half_dx, -half_dy],
                    [half_dx, half_dy],
                    [-half_dx, half_dy]
                ], dtype=np.float32)
                pieces.append({
                    'centroid': centroid,
                    'vertices': vertices_local,
                    'color': (0.5, 0.5, 0.5),
                    'pixel_count': int(dx * dy)
                })
        return pieces

    # Extract features
    ys = coords[:, 0].astype(np.float32)
    xs = coords[:, 1].astype(np.float32)
    
    # Convert BGR/RGB to CIELAB for perceptually uniform color clustering
    img_lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    colors = img_lab[coords[:, 0], coords[:, 1]].astype(np.float32)
    
    # Normalize Lab to [0, 1] range roughly
    colors[:, 0] /= 100.0
    colors[:, 1] = (colors[:, 1] + 128.0) / 255.0
    colors[:, 2] = (colors[:, 2] + 128.0) / 255.0
    
    # Spatial weight based on detail sensitivity slider (jitter_factor)
    # High sensitivity -> lower spatial weight (follows color edges closely)
    # Low sensitivity -> higher spatial weight (creates grid-like uniform shapes)
    spatial_weight = 40.0 * (1.0 - jitter_factor) + 8.0
    
    # Build 5D feature matrix: [x_norm * spatial_weight, y_norm * spatial_weight, L, A, B]
    features = np.column_stack([
        (xs / w) * spatial_weight,
        (ys / h) * spatial_weight,
        colors[:, 0],
        colors[:, 1],
        colors[:, 2]
    ]).astype(np.float32)
    
    # Request a larger cluster count to ensure enough clean candidates are generated after filtering
    target_clusters = int(num_pieces * 1.5)
    num_clusters = min(target_clusters, len(features))
    
    # Run cv2.kmeans to get cluster labels for EVERY masked pixel
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 0.02)
    _, labels, centers = cv2.kmeans(
        features, 
        num_clusters, 
        None, 
        criteria, 
        attempts=1, 
        flags=cv2.KMEANS_PP_CENTERS
    )
    
    # Reconstruct 2D Label Map
    label_map = np.full((h, w), -1, dtype=np.int32)
    label_map[coords[:, 0], coords[:, 1]] = labels.flatten()
    
    pieces = []
    
    # Process each cluster to extract a clean polygon piece
    for k in range(num_clusters):
        cluster_mask = (label_map == k).astype(np.uint8) * 255
        
        # Find contours of this cluster region
        contours, _ = cv2.findContours(cluster_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_piece_pixels:
                continue
                
            # Simplify contour to get a clean polygon
            perimeter = cv2.arcLength(contour, True)
            epsilon = 0.006 * perimeter
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            if len(approx) < 3:
                continue
                
            # Ensure the polygon is convex for stable C++ Qt3D mesh index rendering (triangle fan constraint)
            if not cv2.isContourConvex(approx):
                approx = cv2.convexHull(approx)
                if len(approx) < 3:
                    continue
                    
            # Extract coordinates [N, 2]
            vertices = approx[:, 0, :].astype(np.float32)
            
            # Compute centroid using moments
            M = cv2.moments(approx)
            if M['m00'] > 0:
                cx = M['m10'] / M['m00']
                cy = M['m01'] / M['m00']
            else:
                cx = np.mean(vertices[:, 0])
                cy = np.mean(vertices[:, 1])
                
            centroid = (cx, cy)
            
            # Convert vertices to local space relative to centroid
            vertices_local = vertices - centroid
            
            # Calculate representative color (RGB) of the piece inside the contour
            single_piece_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(single_piece_mask, [approx], -1, 255, -1)
            single_piece_mask = cv2.bitwise_and(single_piece_mask, mask)
            
            pixel_count = np.sum(single_piece_mask > 0)
            if pixel_count < min_piece_pixels:
                continue
                
            avg_color = cv2.mean(img_rgb, mask=single_piece_mask)[:3]
            color_rgb = (avg_color[0] / 255.0, avg_color[1] / 255.0, avg_color[2] / 255.0)
            
            pieces.append({
                'centroid': centroid,
                'vertices': vertices_local,
                'color': color_rgb,
                'pixel_count': int(pixel_count)
            })
            
    # Sort pieces by pixel size (descending) and enforce exact target piece count limit
    pieces.sort(key=lambda p: p['pixel_count'], reverse=True)
    pieces = pieces[:num_pieces]
    
    return pieces

def generate_default_silhouette(target_size=(512, 512)):
    """
    Generates a beautiful, colorful programmatic flower silhouette image
    to be used as the default loaded scene.
    """
    w, h = target_size
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    
    # Draw background: dark charcoal (already zero)
    # We want a high-contrast colorful center object.
    center = (w // 2, h // 2)
    
    # Draw radial petal pattern
    num_petals = 8
    radius_x = int(w * 0.3)
    radius_y = int(h * 0.1)
    
    # Draw outer ring of circles (sky blue)
    for i in range(16):
        angle = i * (2 * np.pi / 16)
        cx = int(center[0] + w * 0.38 * np.cos(angle))
        cy = int(center[1] + h * 0.38 * np.sin(angle))
        cv2.circle(canvas, (cx, cy), int(w * 0.04), (100, 180, 255), -1)
        
    # Draw outer ring connection line
    cv2.circle(canvas, center, int(w * 0.38), (80, 140, 220), int(w * 0.01))
    
    # Draw flower petals
    for i in range(num_petals):
        angle_deg = i * (360 / num_petals)
        # Harmonious color palette - neon shades
        # Cyan, Magenta, Pink, Orange, Teal
        hsv_color = np.uint8([[[int(i * (180 / num_petals)), 230, 255]]])
        rgb_color = cv2.cvtColor(hsv_color, cv2.COLOR_HSV2RGB)[0][0]
        color = (int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2]))
        
        cv2.ellipse(canvas, center, (radius_x, radius_y), angle_deg, 0, 360, color, -1)
        
    # Draw central gold core
    cv2.circle(canvas, center, int(w * 0.1), (255, 210, 30), -1)
    # Inner central star
    cv2.circle(canvas, center, int(w * 0.04), (255, 120, 0), -1)
    
    # Preprocess return matching load_and_preprocess_image output
    img_gray = cv2.cvtColor(canvas, cv2.COLOR_RGB2GRAY)
    aspect = w / h
    return canvas, img_gray, aspect
