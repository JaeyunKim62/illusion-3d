import numpy as np

def pixel_to_screen_3d(px, py, w_img, h_img, w_screen, h_screen, z_screen):
    """
    Maps 2D pixel coordinates (px, py) to 3D screen space coordinates at Z = z_screen.
    Note: In 3D space, Y is pointing UP, whereas in image coordinates, Y is pointing DOWN.
    """
    x_s = (px / w_img - 0.5) * w_screen
    y_s = -(py / h_img - 0.5) * h_screen
    return np.array([x_s, y_s, z_screen], dtype=np.float32)

def backproject_vertices(v2d, t, L_ref=np.array([0.0, 0.0, 0.0])):
    """
    Back-projects a set of 2D screen coordinates v2d (N x 3) from reference light source L_ref
    to 3D space using depth factor t.
    V_3D = L_ref + t * (v2d - L_ref)
    """
    return L_ref + t * (v2d - L_ref)

def project_shadow_vertices(v3d, L, z_screen):
    """
    Vectorized projection of 3D vertices v3d (N x 3) onto the screen plane at z = z_screen
    from a dynamic light source L = (Lx, Ly, Lz).
    Returns the projected 3D coordinates (N x 3) on the screen.
    """
    v3d = np.asarray(v3d, dtype=np.float32)
    L = np.asarray(L, dtype=np.float32)
    
    # Avoid division by zero if vertices are at the same depth as the light source
    denoms = v3d[:, 2] - L[2]
    # Replace near-zero values with a small epsilon
    denoms = np.where(np.abs(denoms) < 1e-5, np.sign(denoms) * 1e-5, denoms)
    # Handle absolute zeros
    denoms = np.where(denoms == 0.0, 1e-5, denoms)
    
    ratios = (z_screen - L[2]) / denoms
    
    x_proj = L[0] + (v3d[:, 0] - L[0]) * ratios
    y_proj = L[1] + (v3d[:, 1] - L[1]) * ratios
    z_proj = np.full_like(x_proj, z_screen)
    
    return np.stack([x_proj, y_proj, z_proj], axis=1)

def generate_prism_mesh_data(centroid_3d, vertices_local_2d, t, thickness):
    """
    Generates a 3D extruded prism mesh from 2D local polygon vertices.
    Vertices are relative to centroid_3d. They are scaled by t.
    Returns:
        vertices: np.ndarray (2N x 3) containing 3D vertex coordinates
        indices: np.ndarray (M x 3) containing triangle vertex index triplets
    """
    N = len(vertices_local_2d)
    if N < 3:
        return np.empty((0, 3)), np.empty((0, 3), dtype=np.int32)
    
    # Vertices
    # Scale local 2D vertices by t and place them on front/back planes
    front_z = thickness / 2.0
    back_z = -thickness / 2.0
    
    front_verts = []
    back_verts = []
    for dx, dy in vertices_local_2d:
        front_verts.append([t * dx, t * dy, front_z])
        back_verts.append([t * dx, t * dy, back_z])
        
    front_verts = np.array(front_verts, dtype=np.float32)
    back_verts = np.array(back_verts, dtype=np.float32)
    
    # Combine and shift by centroid_3d
    # Note: the local rotation or alignment is aligned with screen plane
    local_verts = np.vstack([front_verts, back_verts])
    vertices = local_verts + centroid_3d
    
    # Indices
    indices = []
    
    # 1. Front face (Indices 0 to N-1) - triangle fan (CCW)
    for i in range(1, N - 1):
        indices.append([0, i, i + 1])
        
    # 2. Back face (Indices N to 2N-1) - triangle fan (CW to face away)
    # We want indices: N, N + i + 1, N + i
    for i in range(1, N - 1):
        indices.append([N, N + i + 1, N + i])
        
    # 3. Side faces connecting front and back edges
    for i in range(N):
        nxt = (i + 1) % N
        # Quad vertices: i, nxt (front) and i + N, nxt + N (back)
        # Tri 1: i -> nxt -> nxt + N
        indices.append([i, nxt, nxt + N])
        # Tri 2: i -> nxt + N -> i + N
        indices.append([i, nxt + N, i + N])
        
    return vertices, np.array(indices, dtype=np.int32)

def export_to_obj(filepath, pieces, image_w, image_h, screen_w, screen_h, z_screen, t_list, thickness=0.1, L_ref=(0, 0, 0)):
    """
    Exports all 3D glass pieces to a single Wavefront OBJ file.
    """
    L_ref = np.array(L_ref, dtype=np.float32)
    all_vertices = []
    all_faces = []
    vertex_offset = 1 # OBJ index is 1-based
    
    for i, piece in enumerate(pieces):
        t = t_list[i]
        cx, cy = piece['centroid']
        
        # Map centroid to 3D
        c2d_3d = pixel_to_screen_3d(cx, cy, image_w, image_h, screen_w, screen_h, z_screen)
        centroid_3d = backproject_vertices(c2d_3d, t, L_ref)
        
        # Local vertices in physical units
        # Scale local vertices from pixel units to physical screen units
        scale_x = screen_w / image_w
        scale_y = screen_h / image_h
        verts_local_phys = piece['vertices'] * [scale_x, -scale_y] # Negative scale_y due to axis flip
        
        verts, faces = generate_prism_mesh_data(centroid_3d, verts_local_phys, t, thickness)
        
        if len(verts) == 0:
            continue
            
        all_vertices.append(verts)
        all_faces.append(faces + vertex_offset)
        vertex_offset += len(verts)
        
    if len(all_vertices) == 0:
        return False
        
    merged_vertices = np.vstack(all_vertices)
    merged_faces = np.vstack(all_faces)
    
    with open(filepath, 'w') as f:
        f.write("# 3D Stained Glass Shadow Art - Generated OBJ\n")
        f.write(f"# Number of pieces: {len(pieces)}\n\n")
        
        for v in merged_vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            
        f.write("\n")
        
        for face in merged_faces:
            f.write(f"f {face[0]} {face[1]} {face[2]}\n")
            
    return True

def export_to_svg(filepath, pieces, image_w, image_h):
    """
    Exports the 2D layout of the stained glass to an SVG file.
    """
    with open(filepath, 'w') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{image_w}" height="{image_h}" viewBox="0 0 {image_w} {image_h}">\n')
        f.write(f'  <rect width="100%" height="100%" fill="#121212" />\n')
        
        for piece in pieces:
            # Absolute vertices in pixels
            cx, cy = piece['centroid']
            verts_abs = piece['vertices'] + [cx, cy]
            
            # Format points string
            pts_str = " ".join([f"{pt[0]:.2f},{pt[1]:.2f}" for pt in verts_abs])
            
            # Color string
            r, g, b = [int(c * 255) for c in piece['color']]
            color_str = f"rgb({r},{g},{b})"
            
            # Draw polygon
            f.write(f'  <polygon points="{pts_str}" fill="{color_str}" fill-opacity="0.85" stroke="#ffffff" stroke-width="0.8" stroke-linejoin="round" />\n')
            
        f.write('</svg>\n')
    return True
