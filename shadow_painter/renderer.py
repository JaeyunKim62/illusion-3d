import numpy as np
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QColor, QVector3D, QQuaternion
from PySide6.Qt3DCore import Qt3DCore
from PySide6.Qt3DRender import Qt3DRender
from PySide6.Qt3DExtras import Qt3DExtras
import cv2

from shadow_painter.geometry_engine import (
    pixel_to_screen_3d,
    backproject_vertices,
    project_shadow_vertices,
    generate_prism_mesh_data
)

def create_mesh_geometry(vertices, indices, normals=None):
    """
    Creates a Qt3DCore.QGeometry from vertices (Nx3 float32) and indices (Mx3 uint32).
    """
    geometry = Qt3DCore.QGeometry()
    
    # 1. Vertex Position Buffer
    vertex_bytes = QByteArray(vertices.astype(np.float32).tobytes())
    vertex_buffer = Qt3DCore.QBuffer(geometry)
    vertex_buffer.setData(vertex_bytes)
    
    pos_attr = Qt3DCore.QAttribute(geometry)
    pos_attr.setName(Qt3DCore.QAttribute.defaultPositionAttributeName())
    pos_attr.setVertexBaseType(Qt3DCore.QAttribute.VertexBaseType.Float)
    pos_attr.setVertexSize(3)
    pos_attr.setAttributeType(Qt3DCore.QAttribute.AttributeType.VertexAttribute)
    pos_attr.setBuffer(vertex_buffer)
    pos_attr.setByteStride(3 * 4)
    pos_attr.setCount(len(vertices))
    geometry.addAttribute(pos_attr)
    
    # 2. Vertex Normal Buffer (optional but recommended)
    normal_buffer = None
    normal_attr = None
    if normals is not None:
        normal_bytes = QByteArray(normals.astype(np.float32).tobytes())
        normal_buffer = Qt3DCore.QBuffer(geometry)
        normal_buffer.setData(normal_bytes)
        
        normal_attr = Qt3DCore.QAttribute(geometry)
        normal_attr.setName(Qt3DCore.QAttribute.defaultNormalAttributeName())
        normal_attr.setVertexBaseType(Qt3DCore.QAttribute.VertexBaseType.Float)
        normal_attr.setVertexSize(3)
        normal_attr.setAttributeType(Qt3DCore.QAttribute.AttributeType.VertexAttribute)
        normal_attr.setBuffer(normal_buffer)
        normal_attr.setByteStride(3 * 4)
        normal_attr.setCount(len(vertices))
        geometry.addAttribute(normal_attr)
        
    # 3. Index Buffer
    index_bytes = QByteArray(indices.astype(np.uint32).tobytes())
    index_buffer = Qt3DCore.QBuffer(geometry)
    index_buffer.setData(index_bytes)
    
    index_attr = Qt3DCore.QAttribute(geometry)
    index_attr.setAttributeType(Qt3DCore.QAttribute.AttributeType.IndexAttribute)
    index_attr.setVertexBaseType(Qt3DCore.QAttribute.VertexBaseType.UnsignedInt)
    index_attr.setVertexSize(1)
    index_attr.setBuffer(index_buffer)
    index_attr.setCount(indices.size)
    geometry.addAttribute(index_attr)
    
    return geometry, vertex_buffer, index_buffer, pos_attr, index_attr, normal_buffer, normal_attr

def make_flat_shaded_mesh(vertices, indices):
    """
    Duplicates vertices to create flat-shaded faces with unique normals per triangle face.
    """
    flat_verts = []
    flat_normals = []
    for tri in indices:
        v0, v1, v2 = vertices[tri[0]], vertices[tri[1]], vertices[tri[2]]
        # Calculate normal
        n = np.cross(v1 - v0, v2 - v0)
        n_len = np.linalg.norm(n)
        if n_len > 1e-6:
            n = n / n_len
        else:
            n = np.array([0.0, 0.0, 1.0], dtype=np.float32)
            
        flat_verts.extend([v0, v1, v2])
        flat_normals.extend([n, n, n])
        
    flat_verts = np.array(flat_verts, dtype=np.float32)
    flat_normals = np.array(flat_normals, dtype=np.float32)
    flat_indices = np.arange(len(flat_verts), dtype=np.uint32)
    
    return flat_verts, flat_normals, flat_indices


class GlassPieceEntity:
    """
    Manages the 3D entity representing a glass prism piece.
    """
    def __init__(self, parent_entity, centroid_3d, vertices_local_2d, t, thickness, color, alpha=0.7):
        self.entity = Qt3DCore.QEntity(parent_entity)
        self.color = color
        self.alpha = alpha
        
        # 1. Generate local prism vertices and indices
        self.base_vertices, self.base_indices = generate_prism_mesh_data(
            centroid_3d, vertices_local_2d, t, thickness
        )
        
        # 2. Make flat shaded
        flat_verts, flat_norms, flat_inds = make_flat_shaded_mesh(self.base_vertices, self.base_indices)
        self.vertices_3d = self.base_vertices  # Keep 3D coordinates for shadow calculation
        
        self.geometry_renderer = Qt3DRender.QGeometryRenderer(self.entity)
        self.geometry, self.vertex_buffer, self.index_buffer, self.pos_attr, self.index_attr, self.normal_buffer, self.normal_attr = create_mesh_geometry(
            flat_verts, flat_inds, flat_norms
        )
        self.geometry_renderer.setGeometry(self.geometry)
        self.entity.addComponent(self.geometry_renderer)
        
        # 4. Material
        self.material = Qt3DExtras.QPhongAlphaMaterial(self.entity)
        self.material.setDiffuse(QColor.fromRgbF(color[0], color[1], color[2]))
        self.material.setAmbient(QColor.fromRgbF(color[0] * 0.4, color[1] * 0.4, color[2] * 0.4))
        self.material.setSpecular(QColor("white"))
        self.material.setShininess(50.0)
        self.material.setAlpha(alpha)
        self.entity.addComponent(self.material)
        
        # Keep references on the entity itself to prevent GC!
        self.entity.geometry_renderer = self.geometry_renderer
        self.entity.geometry = self.geometry
        self.entity.vertex_buffer = self.vertex_buffer
        self.entity.index_buffer = self.index_buffer
        self.entity.pos_attr = self.pos_attr
        self.entity.index_attr = self.index_attr
        self.entity.normal_buffer = self.normal_buffer
        self.entity.normal_attr = self.normal_attr
        self.entity.material = self.material

    def set_alpha(self, alpha):
        self.alpha = alpha
        self.material.setAlpha(alpha)


class ShadowPieceEntity:
    """
    Manages the 2D shadow entity projected onto the screen.
    Uses dynamic buffer updates for real-time motion.
    """
    def __init__(self, parent_entity, glass_piece, light_pos, z_screen, alpha=0.6):
        self.entity = Qt3DCore.QEntity(parent_entity)
        self.glass_piece = glass_piece
        self.z_screen = z_screen
        self.color = glass_piece.color
        
        # Create geometry renderer
        self.geometry_renderer = Qt3DRender.QGeometryRenderer(self.entity)
        
        # 1. Compute initial projection data
        vertices_3d, indices, normals, enabled = self._compute_projection_data(light_pos)
        self.entity.setEnabled(enabled)
        
        # 2. Create geometry using helper
        self.geometry, self.vertex_buffer, self.index_buffer, self.pos_attr, self.index_attr, self.normal_buffer, self.normal_attr = create_mesh_geometry(
            vertices_3d, indices, normals
        )
        self.geometry_renderer.setGeometry(self.geometry)
        self.entity.addComponent(self.geometry_renderer)
        
        # 3. Material - flat colored shadow with alpha blending
        self.material = Qt3DExtras.QPhongAlphaMaterial(self.entity)
        self.material.setDiffuse(QColor.fromRgbF(self.color[0], self.color[1], self.color[2]))
        # Keep shadow matte
        self.material.setAmbient(QColor.fromRgbF(self.color[0] * 0.8, self.color[1] * 0.8, self.color[2] * 0.8))
        self.material.setSpecular(QColor(0, 0, 0))
        self.material.setShininess(1.0)
        self.material.setAlpha(alpha)
        self.entity.addComponent(self.material)
        
        # Keep references on the entity itself to prevent GC!
        self.entity.geometry_renderer = self.geometry_renderer
        self.entity.geometry = self.geometry
        self.entity.vertex_buffer = self.vertex_buffer
        self.entity.index_buffer = self.index_buffer
        self.entity.pos_attr = self.pos_attr
        self.entity.index_attr = self.index_attr
        self.entity.normal_buffer = self.normal_buffer
        self.entity.normal_attr = self.normal_attr
        self.entity.material = self.material
        
    def _compute_projection_data(self, light_pos):
        # Project all 3D vertices of the prism
        projected = project_shadow_vertices(self.glass_piece.vertices_3d, light_pos, self.z_screen)
        
        # Get 2D convex hull on screen plane
        # Offset slightly from Z to prevent z-fighting: Z = Z_screen - 0.02
        z_offset = self.z_screen - 0.02
        
        hull = cv2.convexHull(projected[:, :2].astype(np.float32))
        hull_pts = hull[:, 0, :]
        N = len(hull_pts)
        
        if N < 3:
            # Dummy data to avoid empty buffer warning
            dummy_verts = np.zeros((3, 3), dtype=np.float32)
            dummy_norms = np.array([[0, 0, -1], [0, 0, -1], [0, 0, -1]], dtype=np.float32)
            dummy_indices = np.array([0, 1, 2], dtype=np.uint32)
            return dummy_verts, dummy_indices, dummy_norms, False
            
        vertices_3d = np.zeros((N, 3), dtype=np.float32)
        vertices_3d[:, :2] = hull_pts
        vertices_3d[:, 2] = z_offset
        
        normals = np.zeros((N, 3), dtype=np.float32)
        normals[:, 2] = -1.0 # Facing camera
        
        # Triangle fan index array - both winding orders (CW & CCW) to prevent any culling issues
        indices = []
        for i in range(1, N - 1):
            indices.append([0, i, i + 1])
            indices.append([0, i + 1, i])
        indices = np.array(indices, dtype=np.uint32)
        
        return vertices_3d, indices, normals, True

    def update_projection(self, light_pos):
        """
        Recomputes shadow projection from light_pos and updates buffers.
        """
        vertices_3d, indices, normals, enabled = self._compute_projection_data(light_pos)
        self.entity.setEnabled(enabled)
        if not enabled:
            return
            
        # Recreate geometry to support dynamic vertex counts cleanly in Qt 3D
        new_geometry, vertex_buffer, index_buffer, pos_attr, index_attr, normal_buffer, normal_attr = create_mesh_geometry(
            vertices_3d, indices, normals
        )
        
        self.geometry_renderer.setGeometry(new_geometry)
        
        # Clean up old references and store new ones to prevent GC
        self.geometry = new_geometry
        self.vertex_buffer = vertex_buffer
        self.index_buffer = index_buffer
        self.pos_attr = pos_attr
        self.index_attr = index_attr
        self.normal_buffer = normal_buffer
        self.normal_attr = normal_attr
        
        self.entity.geometry = new_geometry
        self.entity.vertex_buffer = vertex_buffer
        self.entity.index_buffer = index_buffer
        self.entity.pos_attr = pos_attr
        self.entity.index_attr = index_attr
        self.entity.normal_buffer = normal_buffer
        self.entity.normal_attr = normal_attr


class ScreenGridEntity:
    """
    Renders a grid of lines slightly in front of the screen plane
    to clarify the target surface and boundaries.
    """
    def __init__(self, parent_entity, w, h, z, divisions=10):
        self.entity = Qt3DCore.QEntity(parent_entity)
        self.geometry_renderer = Qt3DRender.QGeometryRenderer(self.entity)
        self.geometry_renderer.setPrimitiveType(Qt3DRender.QGeometryRenderer.Lines)
        self.entity.addComponent(self.geometry_renderer)
        
        # Grid material - thin emissive light gray lines
        self.material = Qt3DExtras.QPhongMaterial(self.entity)
        self.material.setAmbient(QColor(180, 180, 185, 80))
        self.material.setDiffuse(QColor(180, 180, 185, 80))
        self.material.setSpecular(QColor(0, 0, 0))
        self.entity.addComponent(self.material)
        
        self.update_grid(w, h, z, divisions)
        
        # Prevent GC
        self.entity.renderer = self.geometry_renderer
        self.entity.material = self.material

    def update_grid(self, w, h, z, divisions=10):
        # Slightly offset to prevent z-fighting with screen plane
        z_offset = z - 0.005
        
        verts = []
        # Vertical lines
        x_coords = np.linspace(-w/2, w/2, divisions + 1)
        for x in x_coords:
            verts.append([x, -h/2, z_offset])
            verts.append([x, h/2, z_offset])
            
        # Horizontal lines
        y_coords = np.linspace(-h/2, h/2, divisions + 1)
        for y in y_coords:
            verts.append([-w/2, y, z_offset])
            verts.append([w/2, y, z_offset])
            
        vertices = np.array(verts, dtype=np.float32)
        indices = np.arange(len(vertices), dtype=np.uint32)
        normals = np.zeros_like(vertices)
        normals[:, 2] = -1.0
        
        self.geometry, self.vertex_buffer, self.index_buffer, self.pos_attr, self.index_attr, self.normal_buffer, self.normal_attr = create_mesh_geometry(vertices, indices, normals)
        self.geometry_renderer.setGeometry(self.geometry)
        
        # Prevent GC on updated buffers by attaching to the entity
        self.entity.geometry = self.geometry
        self.entity.vertex_buffer = self.vertex_buffer
        self.entity.index_buffer = self.index_buffer
        self.entity.pos_attr = self.pos_attr
        self.entity.index_attr = self.index_attr
        self.entity.normal_buffer = self.normal_buffer
        self.entity.normal_attr = self.normal_attr


class StainedGlassRenderer:
    """
    Manages the Qt 3D scene: Camera, Lights, Screen, Glass pieces, Shadows, and Light rays.
    """
    def __init__(self, view_window):
        self.view = view_window
        
        # Root Entity
        self.root_entity = Qt3DCore.QEntity()
        self.view.setRootEntity(self.root_entity)
        
        # Track active entities
        self.glass_entities = []
        self.shadow_entities = []
        self.pieces_root = None
        self.shadows_root = None
        
        # Default Parameters - Light is fixed at (0.0, 0.0, 0.0)
        self.light_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.z_screen = 10.0
        self.screen_width = 10.0
        self.screen_height = 10.0
        self.ray_visualization = False
        
        # Setup Scene
        self._setup_camera()
        self._setup_lighting()
        self._setup_screen()
        self._setup_ray_visualizer()
        
    def _setup_camera(self):
        # Camera
        self.camera = self.view.camera()
        self.camera.lens().setPerspectiveProjection(45.0, 1.0, 0.1, 1000.0)
        self.camera.setPosition(QVector3D(0.0, 0.0, -12.0))
        self.camera.setViewCenter(QVector3D(0.0, 0.0, 5.0))
        
        # Camera Controller
        self.camera_controller = Qt3DExtras.QOrbitCameraController(self.root_entity)
        self.camera_controller.setCamera(self.camera)
        self.camera_controller.setLookSpeed(180.0)
        self.camera_controller.setLinearSpeed(50.0)
        
    def _setup_lighting(self):
        # Point Light Entity
        self.light_entity = Qt3DCore.QEntity(self.root_entity)
        self.light = Qt3DRender.QPointLight(self.light_entity)
        self.light.setColor(QColor("white"))
        self.light.setIntensity(1.8)
        self.light_entity.addComponent(self.light)
        
        self.light_transform = Qt3DCore.QTransform(self.light_entity)
        self.light_transform.setTranslation(QVector3D(self.light_pos[0], self.light_pos[1], self.light_pos[2]))
        self.light_entity.addComponent(self.light_transform)
        
        # Keep references to prevent GC
        self.light_entity.light = self.light
        self.light_entity.transform = self.light_transform
        
        # Light Bulb Sphere (visual indicator)
        self.bulb_entity = Qt3DCore.QEntity(self.root_entity)
        self.bulb_mesh = Qt3DExtras.QSphereMesh(self.bulb_entity)
        self.bulb_mesh.setRadius(0.15)
        self.bulb_material = Qt3DExtras.QPhongMaterial(self.bulb_entity)
        self.bulb_material.setAmbient(QColor(255, 255, 230))
        self.bulb_material.setDiffuse(QColor(255, 255, 230))
        self.bulb_entity.addComponent(self.bulb_mesh)
        self.bulb_entity.addComponent(self.bulb_material)
        
        self.bulb_transform = Qt3DCore.QTransform(self.bulb_entity)
        self.bulb_transform.setTranslation(QVector3D(self.light_pos[0], self.light_pos[1], self.light_pos[2]))
        self.bulb_entity.addComponent(self.bulb_transform)
        
        # Keep references to prevent GC
        self.bulb_entity.mesh = self.bulb_mesh
        self.bulb_entity.material = self.bulb_material
        self.bulb_entity.transform = self.bulb_transform
        
    def _setup_screen(self):
        self.screen_entity = Qt3DCore.QEntity(self.root_entity)
        
        # Custom screen plane geometry to avoid rotation issues
        self.screen_geometry_renderer = Qt3DRender.QGeometryRenderer(self.screen_entity)
        self.frame_entities = [] # Track frame borders
        self._update_screen_mesh()
        self.screen_entity.addComponent(self.screen_geometry_renderer)
        
        # Screen Material - Matte white gallery wall
        self.screen_material = Qt3DExtras.QPhongMaterial(self.screen_entity)
        self.screen_material.setAmbient(QColor(240, 240, 242))
        self.screen_material.setDiffuse(QColor(255, 255, 255))
        self.screen_material.setSpecular(QColor(5, 5, 5))
        self.screen_material.setShininess(1.0)
        self.screen_entity.addComponent(self.screen_material)
        
        # Keep references to prevent GC
        self.screen_entity.geometry_renderer = self.screen_geometry_renderer
        self.screen_entity.material = self.screen_material
        
    def _update_screen_mesh(self):
        w = self.screen_width
        h = self.screen_height
        z = self.z_screen
        
        # Create a massive background plane representing the gallery wall
        wall_w = 60.0
        wall_h = 60.0
        
        vertices = np.array([
            [-wall_w/2, -wall_h/2, z],
            [wall_w/2, -wall_h/2, z],
            [wall_w/2, wall_h/2, z],
            [-wall_w/2, wall_h/2, z]
        ], dtype=np.float32)
        
        normals = np.array([
            [0, 0, -1],
            [0, 0, -1],
            [0, 0, -1],
            [0, 0, -1]
        ], dtype=np.float32)
        
        indices = np.array([
            [0, 1, 2],
            [0, 2, 3]
        ], dtype=np.uint32)
        
        self.screen_geometry, self.screen_vertex_buffer, self.screen_index_buffer, self.screen_pos_attr, self.screen_index_attr, self.screen_normal_buffer, self.screen_normal_attr = create_mesh_geometry(vertices, indices, normals)
        self.screen_geometry_renderer.setGeometry(self.screen_geometry)
        
        # Update or create the grid overlay on the screen boundaries inside the frame
        if not hasattr(self, 'screen_grid'):
            self.screen_grid = ScreenGridEntity(self.screen_entity, w, h, z, divisions=10)
        else:
            self.screen_grid.update_grid(w, h, z, divisions=10)
            
        self._update_screen_frame()
        
        # Keep references on screen_entity to prevent GC
        self.screen_entity.geometry = self.screen_geometry
        self.screen_entity.vertex_buffer = self.screen_vertex_buffer
        self.screen_entity.index_buffer = self.screen_index_buffer
        self.screen_entity.pos_attr = self.screen_pos_attr
        self.screen_entity.index_attr = self.screen_index_attr
        self.screen_entity.normal_buffer = self.screen_normal_buffer
        self.screen_entity.normal_attr = self.screen_normal_attr

    def _update_screen_frame(self):
        # Clear old frame entities if any
        for entity in self.frame_entities:
            entity.setParent(None)
        self.frame_entities = []
        
        w = self.screen_width
        h = self.screen_height
        z = self.z_screen
        thickness = 0.15 # Visual width of the frame border
        depth = 0.08 # Depth thickness
        
        # Elegant brass/bronze metallic material for screen frame
        frame_material = Qt3DExtras.QPhongMaterial(self.screen_entity)
        frame_material.setAmbient(QColor(40, 35, 30))
        frame_material.setDiffuse(QColor(95, 80, 60))
        frame_material.setSpecular(QColor(240, 205, 140))
        frame_material.setShininess(35.0)
        
        # 1. Top
        self.frame_entities.append(self._create_frame_box(0.0, h/2 + thickness/2, z, w + thickness*2, thickness, depth, frame_material))
        # 2. Bottom
        self.frame_entities.append(self._create_frame_box(0.0, -h/2 - thickness/2, z, w + thickness*2, thickness, depth, frame_material))
        # 3. Left
        self.frame_entities.append(self._create_frame_box(-w/2 - thickness/2, 0.0, z, thickness, h, depth, frame_material))
        # 4. Right
        self.frame_entities.append(self._create_frame_box(w/2 + thickness/2, 0.0, z, thickness, h, depth, frame_material))

    def _create_frame_box(self, tx, ty, tz, sx, sy, sz, material):
        entity = Qt3DCore.QEntity(self.screen_entity)
        mesh = Qt3DExtras.QCuboidMesh(entity)
        mesh.setXExtent(sx)
        mesh.setYExtent(sy)
        mesh.setZExtent(sz)
        
        transform = Qt3DCore.QTransform(entity)
        transform.setTranslation(QVector3D(tx, ty, tz))
        
        entity.addComponent(mesh)
        entity.addComponent(transform)
        entity.addComponent(material)
        
        # Keep component references to prevent GC!
        entity.mesh = mesh
        entity.transform = transform
        entity.material = material
        
        return entity
        
    def _setup_ray_visualizer(self):
        """
        Renders faint projection lines from the light source to each piece.
        """
        self.rays_entity = Qt3DCore.QEntity(self.root_entity)
        self.rays_renderer = Qt3DRender.QGeometryRenderer(self.rays_entity)
        self.rays_renderer.setPrimitiveType(Qt3DRender.QGeometryRenderer.Lines)
        self.rays_entity.addComponent(self.rays_renderer)
        
        # Custom ray geometry - Keep parentless to avoid cyclic parenting loop
        self.rays_geometry = Qt3DCore.QGeometry()
        self.rays_vertex_buffer = Qt3DCore.QBuffer(self.rays_geometry)
        self.rays_normal_buffer = Qt3DCore.QBuffer(self.rays_geometry)
        
        self.rays_pos_attr = Qt3DCore.QAttribute(self.rays_geometry)
        self.rays_pos_attr.setName(Qt3DCore.QAttribute.defaultPositionAttributeName())
        self.rays_pos_attr.setVertexBaseType(Qt3DCore.QAttribute.VertexBaseType.Float)
        self.rays_pos_attr.setVertexSize(3)
        self.rays_pos_attr.setAttributeType(Qt3DCore.QAttribute.AttributeType.VertexAttribute)
        self.rays_pos_attr.setBuffer(self.rays_vertex_buffer)
        self.rays_pos_attr.setByteStride(3 * 4)
        self.rays_geometry.addAttribute(self.rays_pos_attr)
        
        self.rays_normal_attr = Qt3DCore.QAttribute(self.rays_geometry)
        self.rays_normal_attr.setName(Qt3DCore.QAttribute.defaultNormalAttributeName())
        self.rays_normal_attr.setVertexBaseType(Qt3DCore.QAttribute.VertexBaseType.Float)
        self.rays_normal_attr.setVertexSize(3)
        self.rays_normal_attr.setAttributeType(Qt3DCore.QAttribute.AttributeType.VertexAttribute)
        self.rays_normal_attr.setBuffer(self.rays_normal_buffer)
        self.rays_normal_attr.setByteStride(3 * 4)
        self.rays_geometry.addAttribute(self.rays_normal_attr)
        
        self.rays_index_buffer = Qt3DCore.QBuffer(self.rays_geometry)
        self.rays_index_attr = Qt3DCore.QAttribute(self.rays_geometry)
        self.rays_index_attr.setAttributeType(Qt3DCore.QAttribute.AttributeType.IndexAttribute)
        self.rays_index_attr.setVertexBaseType(Qt3DCore.QAttribute.VertexBaseType.UnsignedInt)
        self.rays_index_attr.setVertexSize(1)
        self.rays_index_attr.setBuffer(self.rays_index_buffer)
        self.rays_geometry.addAttribute(self.rays_index_attr)
        
        self.rays_renderer.setGeometry(self.rays_geometry)
        
        # Initialize with dummy data to prevent Metal pipeline creation failure on empty buffers
        dummy_verts = np.zeros((2, 3), dtype=np.float32)
        dummy_norms = np.zeros((2, 3), dtype=np.float32)
        dummy_norms[:, 2] = -1.0
        dummy_indices = np.array([0, 1], dtype=np.uint32)
        
        self.rays_vertex_buffer.setData(QByteArray(dummy_verts.tobytes()))
        self.rays_normal_buffer.setData(QByteArray(dummy_norms.tobytes()))
        self.rays_index_buffer.setData(QByteArray(dummy_indices.tobytes()))
        
        self.rays_pos_attr.setCount(2)
        self.rays_normal_attr.setCount(2)
        self.rays_index_attr.setCount(2)
        
        # Ray material - emissive faint yellow lines
        self.rays_material = Qt3DExtras.QPhongMaterial(self.rays_entity)
        self.rays_material.setAmbient(QColor(255, 255, 200, 40))
        self.rays_material.setDiffuse(QColor(255, 255, 200, 40))
        self.rays_material.setSpecular(QColor(0, 0, 0))
        self.rays_entity.addComponent(self.rays_material)
        self.rays_entity.setEnabled(False)
        
        # Keep references to prevent GC!
        self.rays_entity.renderer = self.rays_renderer
        self.rays_entity.material = self.rays_material
        self.rays_entity.geometry = self.rays_geometry
        self.rays_entity.vertex_buffer = self.rays_vertex_buffer
        self.rays_entity.normal_buffer = self.rays_normal_buffer
        self.rays_entity.index_buffer = self.rays_index_buffer
        self.rays_entity.pos_attr = self.rays_pos_attr
        self.rays_entity.normal_attr = self.rays_normal_attr
        self.rays_entity.index_attr = self.rays_index_attr
        
    def rebuild_scene(self, pieces, image_w, image_h, screen_w, z_screen, t_list, thickness, glass_alpha, show_shadows=True):
        """
        Recreates all glass piece entities and shadow entities in the scene.
        """
        self.z_screen = z_screen
        self.screen_width = screen_w
        self.screen_height = screen_w * (image_h / image_w)
        
        # 1. Update the screen plane mesh
        self._update_screen_mesh()
        
        # 2. Clear old entities
        if self.pieces_root:
            self.pieces_root.setParent(None)
        if self.shadows_root:
            self.shadows_root.setParent(None)
            
        self.glass_entities = []
        self.shadow_entities = []
        
        # Create new sub-roots
        self.pieces_root = Qt3DCore.QEntity(self.root_entity)
        self.shadows_root = Qt3DCore.QEntity(self.root_entity)
        self.shadows_root.setEnabled(show_shadows)
        
        # 3. Build new glass pieces & shadow entities
        L_ref = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        scale_x = self.screen_width / image_w
        scale_y = self.screen_height / image_h
        
        for i, piece in enumerate(pieces):
            t = t_list[i]
            cx, cy = piece['centroid']
            
            # Map centroid to screen coordinates in 3D
            c2d_3d = pixel_to_screen_3d(cx, cy, image_w, image_h, self.screen_width, self.screen_height, self.z_screen)
            centroid_3d = backproject_vertices(c2d_3d, t, L_ref)
            
            # Transform local piece vertices to physical coordinates
            verts_local_phys = piece['vertices'] * [scale_x, -scale_y]
            
            # Create Glass Piece
            glass_piece = GlassPieceEntity(
                self.pieces_root, centroid_3d, verts_local_phys, t, thickness, piece['color'], glass_alpha
            )
            self.glass_entities.append(glass_piece)
            
            # Create corresponding Shadow Piece
            shadow_piece = ShadowPieceEntity(
                self.shadows_root, glass_piece, self.light_pos, self.z_screen, alpha=0.75
            )
            self.shadow_entities.append(shadow_piece)
            
        # 4. Update rays
        self.update_rays()
        
    def set_light_enabled(self, enabled):
        """
        Enables or disables the spotlight source and dynamically updates the bulb's visual state.
        """
        self.light_entity.setEnabled(enabled)
        
        # Change the bulb material's color based on the light state
        if enabled:
            self.bulb_material.setAmbient(QColor(255, 255, 230))
            self.bulb_material.setDiffuse(QColor(255, 255, 230))
        else:
            self.bulb_material.setAmbient(QColor(40, 40, 45))
            self.bulb_material.setDiffuse(QColor(40, 40, 45))

    def set_light_position(self, x, y, z):
        """
        Updates the 3D position of the point light, its visual sphere, and projects shadows.
        """
        self.light_pos = np.array([x, y, z], dtype=np.float32)
        pos = QVector3D(x, y, z)
        self.light_transform.setTranslation(pos)
        self.bulb_transform.setTranslation(pos)
        
        # Dynamic shadow update
        for shadow in self.shadow_entities:
            shadow.update_projection(self.light_pos)
            
        # Dynamic rays update
        self.update_rays()
        
    def set_glass_alpha(self, alpha):
        for glass in self.glass_entities:
            glass.set_alpha(alpha)
            
    def set_shadows_enabled(self, enabled):
        if self.shadows_root:
            self.shadows_root.setEnabled(enabled)
            
    def set_rays_enabled(self, enabled):
        self.ray_visualization = enabled
        self.rays_entity.setEnabled(enabled)
        if enabled:
            self.update_rays()
            
    def update_rays(self):
        """
        Updates the line buffers for the light rays.
        """
        if not self.ray_visualization or len(self.glass_entities) == 0:
            return
            
        K = len(self.glass_entities)
        vertices = np.zeros((2 * K, 3), dtype=np.float32)
        normals = np.zeros((2 * K, 3), dtype=np.float32)
        normals[:, 2] = -1.0 # Facing camera
        indices = np.arange(2 * K, dtype=np.uint32)
        
        for k, glass in enumerate(self.glass_entities):
            # Centroid of glass piece is in glass.vertices_3d
            centroid = np.mean(glass.vertices_3d, axis=0)
            
            # Line connects light_pos to glass centroid
            vertices[2 * k] = self.light_pos
            vertices[2 * k + 1] = centroid
            
        self.rays_vertex_buffer.setData(QByteArray(vertices.tobytes()))
        self.rays_normal_buffer.setData(QByteArray(normals.tobytes()))
        self.rays_index_buffer.setData(QByteArray(indices.tobytes()))
        
        self.rays_pos_attr.setCount(2 * K)
        self.rays_normal_attr.setCount(2 * K)
        self.rays_index_attr.setCount(2 * K)
        
    def reset_camera(self):
        self.camera.setPosition(QVector3D(0.0, 0.0, -12.0))
        self.camera.setViewCenter(QVector3D(0.0, 0.0, 5.0))
        self.camera.setUpVector(QVector3D(0.0, 1.0, 0.0))

    def set_camera_angles(self, yaw, pitch):
        """
        Sets the camera position based on yaw (azimuth) and pitch (elevation) angles.
        Rotates along a sphere centered at camera.viewCenter().
        """
        center = self.camera.viewCenter()
        pos = self.camera.position()
        d = (pos - center).length()
        if d < 0.1:
            d = 17.0 # Default fallback distance
            
        # Clamp pitch to prevent going past the poles
        pitch = np.clip(pitch, -np.pi/2 + 0.05, np.pi/2 - 0.05)
        
        # Calculate new offset relative to center
        # Yaw (horizontal): Y-axis rotation
        # Pitch (vertical): X-axis rotation
        dx = d * np.cos(pitch) * np.sin(yaw)
        dy = d * np.sin(pitch)
        dz = -d * np.cos(pitch) * np.cos(yaw)
        
        new_pos = QVector3D(center.x() + dx, center.y() + dy, center.z() + dz)
        self.camera.setPosition(new_pos)
        self.camera.setUpVector(QVector3D(0.0, 1.0, 0.0))
