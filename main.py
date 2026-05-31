import sys
import json
import os
import numpy as np

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QSurfaceFormat
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QDoubleSpinBox, QSpinBox, QPushButton, QFrame,
    QSplitter, QGroupBox, QGridLayout
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

# PyOpenGL Imports
from OpenGL.GL import *
from OpenGL.GL import shaders

# Modern styling configurations (QSS)
DARK_STYLE = """
QMainWindow {
    background-color: #0c0c10;
}

QWidget {
    font-family: 'Segoe UI', 'Outfit', 'Inter', -apple-system, sans-serif;
    color: #e2e8f0;
}

QFrame#sidebarFrame {
    background-color: #13131a;
    border-right: 1px solid #23232f;
}

QGroupBox {
    font-weight: bold;
    font-size: 13px;
    border: 1px solid #23232f;
    border-radius: 8px;
    margin-top: 15px;
    padding-top: 10px;
    background-color: #171721;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: #8f9bff;
}

QLabel {
    font-size: 12px;
    color: #94a3b8;
}

QLabel#titleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
    margin-bottom: 5px;
}

QLabel#subtitleLabel {
    font-size: 11px;
    color: #64748b;
    margin-bottom: 15px;
}

QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #27273a;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8f9bff, stop:1 #4f46e5);
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #a5b4fc, stop:1 #6366f1);
}

QDoubleSpinBox {
    background-color: #0c0c10;
    color: #f8fafc;
    border: 1px solid #23232f;
    border-radius: 5px;
    padding: 2px 5px;
    font-size: 11px;
    min-width: 60px;
}

QDoubleSpinBox:focus {
    border: 1px solid #4f46e5;
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #232335, stop:1 #1c1c2b);
    color: #ffffff;
    border: 1px solid #2d2d42;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: bold;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2a2a42, stop:1 #232335);
    border: 1px solid #4f46e5;
}

QPushButton:pressed {
    background-color: #0c0c10;
}

/* Specific button styles */
QPushButton#resetBtn {
    border-color: #ef4444;
    color: #fca5a5;
}
QPushButton#resetBtn:hover {
    background: #2d1a1a;
}
"""


# --- NumPy 3D Matrix Utilities ---
def perspective_matrix(fovy, aspect, near, far):
    f = 1.0 / np.tan(np.radians(fovy) / 2.0)
    proj = np.zeros((4, 4), dtype=np.float32)
    proj[0, 0] = f / aspect
    proj[1, 1] = f
    proj[2, 2] = (far + near) / (near - far)
    proj[2, 3] = (2.0 * far * near) / (near - far)
    proj[3, 2] = -1.0
    return proj.T  # Transposed for OpenGL (column-major)

def translation_matrix(x, y, z):
    mat = np.eye(4, dtype=np.float32)
    mat[0, 3] = x
    mat[1, 3] = y
    mat[2, 3] = z
    return mat.T

def rotation_x_matrix(angle):
    rad = np.radians(angle)
    c, s = np.cos(rad), np.sin(rad)
    mat = np.eye(4, dtype=np.float32)
    mat[1, 1] = c
    mat[1, 2] = -s
    mat[2, 1] = s
    mat[2, 2] = c
    return mat.T

def rotation_y_matrix(angle):
    rad = np.radians(angle)
    c, s = np.cos(rad), np.sin(rad)
    mat = np.eye(4, dtype=np.float32)
    mat[0, 0] = c
    mat[0, 2] = s
    mat[2, 0] = -s
    mat[2, 2] = c
    return mat.T


def compile_shader_program(vertex_code, fragment_code):
    # Compile Vertex Shader
    vs = glCreateShader(GL_VERTEX_SHADER)
    glShaderSource(vs, vertex_code)
    glCompileShader(vs)
    if not glGetShaderiv(vs, GL_COMPILE_STATUS):
        info = glGetShaderInfoLog(vs)
        glDeleteShader(vs)
        raise RuntimeError(f"Vertex shader compilation failed: {info.decode('utf-8')}")
        
    # Compile Fragment Shader
    fs = glCreateShader(GL_FRAGMENT_SHADER)
    glShaderSource(fs, fragment_code)
    glCompileShader(fs)
    if not glGetShaderiv(fs, GL_COMPILE_STATUS):
        info = glGetShaderInfoLog(fs)
        glDeleteShader(vs)
        glDeleteShader(fs)
        raise RuntimeError(f"Fragment shader compilation failed: {info.decode('utf-8')}")
        
    # Link Program
    program = glCreateProgram()
    glAttachShader(program, vs)
    glAttachShader(program, fs)
    glLinkProgram(program)
    
    # Check link status
    if not glGetProgramiv(program, GL_LINK_STATUS):
        info = glGetProgramInfoLog(program)
        glDeleteShader(vs)
        glDeleteShader(fs)
        glDeleteProgram(program)
        raise RuntimeError(f"Shader program link failed: {info.decode('utf-8')}")
        
    # Cleanup individual shaders
    glDeleteShader(vs)
    glDeleteShader(fs)
    
    return program


class PointCloudWidget(QOpenGLWidget):
    # Signals for synchronization back to UI
    camera_changed = Signal(float, float, float) # yaw, pitch, distance

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = np.empty((0, 3), dtype=np.float32)
        self.scale = 1.0
        
        # Adjustable parameters
        self.point_size = 0.03                     # World size diameter of spheres
        self.light_pos_world = np.array([2.0, 2.0, 2.0], dtype=np.float32) # World light position
        self.point_color = np.array([0.3, 0.6, 1.0], dtype=np.float32)     # Spheres color
        
        # Interactive Camera states
        self.yaw = -45.0
        self.pitch = 30.0
        self.distance = 2.5
        self.pan_x = 0.0
        self.pan_y = 0.0
        
        self.last_mouse_pos = None
        
        # GL handles
        self.shader_program = None
        self.vao = None
        self.vbo = None
        self.light_vao = None
        self.light_vbo = None

    def set_points(self, points):
        self.points = points.astype(np.float32)
        if self.isValid():
            self.makeCurrent()
            self.upload_data()
            self.doneCurrent()
            self.update()

    def upload_data(self):
        if self.points.size == 0:
            return
            
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.points.nbytes, self.points.tobytes(), GL_STATIC_DRAW)
        
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def upload_light_data(self):
        if not self.light_vao or not self.light_vbo:
            return
        glBindVertexArray(self.light_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.light_vbo)
        glBufferData(GL_ARRAY_BUFFER, self.light_pos_world.nbytes, self.light_pos_world.tobytes(), GL_DYNAMIC_DRAW)
        
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def initializeGL(self):
        self.gl = self.context().extraFunctions()
        self.gl.initializeOpenGLFunctions()
        
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)
        
        # Ensure shader can write to gl_PointSize
        glEnable(GL_PROGRAM_POINT_SIZE)
        
        # Blend config for alpha-based edges (makes discard edges cleaner on some displays)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # --- GLSL Shader source code ---
        # Draw smooth shaded 3D spheres from flat point sprites
        vertex_shader_source = """
        #version 330 core
        layout (location = 0) in vec3 aPos;
        
        uniform mat4 u_projection;
        uniform mat4 u_view;
        uniform mat4 u_model;
        uniform float u_pointSize;       // Sphere physical diameter in world units
        uniform float u_viewportHeight;  // Viewport height in pixels
        
        out vec3 v_viewPos;              // Vertex pos in View Space
        
        void main() {
            vec4 viewPos = u_view * u_model * vec4(aPos, 1.0);
            v_viewPos = viewPos.xyz;
            gl_Position = u_projection * viewPos;
            
            // Sphere scaling based on perspective depth
            float dist = max(-viewPos.z, 0.001);
            gl_PointSize = (u_pointSize * u_projection[1][1] * u_viewportHeight) / dist;
            
            // Limit minimum/maximum point size
            if (gl_PointSize < 1.0) gl_PointSize = 1.0;
        }
        """
        
        fragment_shader_source = """
        #version 330 core
        in vec3 v_viewPos;
        
        uniform mat4 u_projection;
        uniform float u_pointSize;       // Physical size in world space
        uniform vec3 u_lightPos;         // Light position in View Space
        uniform vec3 u_pointColor;       // Base diffuse color
        uniform int u_renderMode;        // 0: Point Cloud, 1: Glowing Light, 2: Flat Lines
        
        out vec4 FragColor;
        
        void main() {
            if (u_renderMode == 2) {
                // Emissive solid color for lines (Ignore lighting and point sprite texture coords)
                FragColor = vec4(u_pointColor, 1.0);
                return;
            }
            
            // Convert Point Coord (0.0 to 1.0) to centered coord (-1.0 to 1.0)
            vec2 normalCoords = gl_PointCoord * 2.0 - 1.0;
            
            // Discard fragments outside the sphere's circle silhouette
            float r2 = dot(normalCoords, normalCoords);
            if (r2 > 1.0) {
                discard;
            }
            
            // Compute artificial 3D normal vector of the sphere surface
            float z = sqrt(1.0 - r2);
            vec3 normal = normalize(vec3(normalCoords.x, -normalCoords.y, z));
            
            if (u_renderMode == 1) {
                // Glow effect for light source
                float centerGlow = pow(1.0 - r2, 2.0);
                vec3 glowColor = mix(vec3(1.0, 0.95, 0.5), vec3(1.0, 1.0, 1.0), centerGlow);
                FragColor = vec4(glowColor, 1.0);
                
                // Depth correction
                float sphereRadius = u_pointSize / 2.0;
                float pixelDepth = v_viewPos.z + z * sphereRadius;
                float denom = max(-pixelDepth, 0.0001);
                float ndcDepth = (u_projection[2][2] * pixelDepth + u_projection[3][2]) / denom;
                gl_FragDepth = ndcDepth * 0.5 + 0.5;
                return;
            }
            
            // Calculate light shading in View Space (u_renderMode == 0)
            vec3 L = normalize(u_lightPos - v_viewPos);
            
            // Ambient component
            float ambient = 0.25;
            
            // Diffuse component
            float diffuse = max(dot(normal, L), 0.0);
            
            // Specular highlight
            vec3 V = normalize(-v_viewPos);
            vec3 R = reflect(-L, normal);
            float spec = pow(max(dot(R, V), 0.0), 32.0) * 0.4;
            
            vec3 finalColor = u_pointColor * (ambient + diffuse) + vec3(spec);
            FragColor = vec4(finalColor, 1.0);
            
            // Pixel depth correction for correct 3D intersection/stacking
            float sphereRadius = u_pointSize / 2.0;
            float pixelDepth = v_viewPos.z + z * sphereRadius;
            float denom = max(-pixelDepth, 0.0001);
            float ndcDepth = (u_projection[2][2] * pixelDepth + u_projection[3][2]) / denom;
            gl_FragDepth = ndcDepth * 0.5 + 0.5;
        }
        """
        
        try:
            self.shader_program = compile_shader_program(vertex_shader_source, fragment_shader_source)
        except Exception as e:
            print("Shader Compilation Error:")
            print(e)
            sys.exit(1)
            
        # Create buffers
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.upload_data()
        
        # Create buffers for light visualization
        self.light_vao = glGenVertexArrays(1)
        self.light_vbo = glGenBuffers(1)
        self.upload_light_data()

    def paintGL(self):
        glClearColor(0.08, 0.08, 0.12, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        if self.points.size == 0 or not self.shader_program:
            return
            
        glUseProgram(self.shader_program)
        
        # --- Generate Matrices ---
        width = max(self.width(), 1)
        height = max(self.height(), 1)
        aspect = width / height
        projection = perspective_matrix(45.0, aspect, 0.1, 100.0)
        
        # Orbit camera around origin (0, 0, 0): rotate Y -> rotate X -> translate to distance and apply panning
        # In transposed column-major math: view_transposed = R_y^T @ R_x^T @ T^T
        view = (rotation_y_matrix(self.yaw) @ 
                rotation_x_matrix(self.pitch) @ 
                translation_matrix(self.pan_x, self.pan_y, -self.distance))
        
        model = np.eye(4, dtype=np.float32)
        
        # Transform Light Position into View Space (use view.T which represents the non-transposed View matrix)
        light_pos_world4 = np.array([self.light_pos_world[0], self.light_pos_world[1], self.light_pos_world[2], 1.0], dtype=np.float32)
        light_pos_view = view.T @ light_pos_world4
        
        # Upload uniforms
        glUniformMatrix4fv(glGetUniformLocation(self.shader_program, "u_projection"), 1, GL_FALSE, projection)
        glUniformMatrix4fv(glGetUniformLocation(self.shader_program, "u_view"), 1, GL_FALSE, view)
        glUniformMatrix4fv(glGetUniformLocation(self.shader_program, "u_model"), 1, GL_FALSE, model)
        
        glUniform1f(glGetUniformLocation(self.shader_program, "u_viewportHeight"), float(self.height()))
        glUniform3f(glGetUniformLocation(self.shader_program, "u_lightPos"), 
                    light_pos_view[0], light_pos_view[1], light_pos_view[2])
        
        # 1. Draw Point Cloud
        glUniform1i(glGetUniformLocation(self.shader_program, "u_renderMode"), 0)
        glUniform1f(glGetUniformLocation(self.shader_program, "u_pointSize"), self.point_size)
        glUniform3f(glGetUniformLocation(self.shader_program, "u_pointColor"), 
                    self.point_color[0], self.point_color[1], self.point_color[2])
                    
        glBindVertexArray(self.vao)
        glDrawArrays(GL_POINTS, 0, len(self.points))
        glBindVertexArray(0)
        
        # 2. Draw Glowing Light Source
        glUniform1i(glGetUniformLocation(self.shader_program, "u_renderMode"), 1)
        # Give light source sphere an increased visual diameter
        glUniform1f(glGetUniformLocation(self.shader_program, "u_pointSize"), self.point_size * 2.0)
        
        self.upload_light_data()
        glBindVertexArray(self.light_vao)
        glDrawArrays(GL_POINTS, 0, 1)
        glBindVertexArray(0)
        
        # 3. Draw Virtual Coordinate Axis Lines (Helper lines)
        glUniform1i(glGetUniformLocation(self.shader_program, "u_renderMode"), 2)
        
        # X-Axis (Red)
        axis_x = np.array([[-1.5 * self.scale, 0.0, 0.0], [1.5 * self.scale, 0.0, 0.0]], dtype=np.float32)
        self.draw_temp_line(axis_x, np.array([0.9, 0.3, 0.3], dtype=np.float32))
        
        # Y-Axis (Green)
        axis_y = np.array([[0.0, -1.5 * self.scale, 0.0], [0.0, 1.5 * self.scale, 0.0]], dtype=np.float32)
        self.draw_temp_line(axis_y, np.array([0.3, 0.9, 0.3], dtype=np.float32))
        
        # Z-Axis (Blue)
        axis_z = np.array([[0.0, 0.0, -1.5 * self.scale], [0.0, 0.0, 1.5 * self.scale]], dtype=np.float32)
        self.draw_temp_line(axis_z, np.array([0.3, 0.3, 0.9], dtype=np.float32))
        
        # 4. Draw Spherical Light Orbit Ring (Solid yellow-ish circle)
        orbit_ring = self.get_orbit_ring_vertices()
        self.draw_temp_loop(orbit_ring, np.array([0.8, 0.8, 0.4], dtype=np.float32))
        
        # 5. Draw Light Pointer Vector Line (Origin to light source)
        pointer_line = np.array([[0.0, 0.0, 0.0], self.light_pos_world], dtype=np.float32)
        self.draw_temp_line(pointer_line, np.array([1.0, 1.0, 0.5], dtype=np.float32))
        
        glUseProgram(0)

    def draw_temp_line(self, vertices, color):
        glUniform3f(glGetUniformLocation(self.shader_program, "u_pointColor"), color[0], color[1], color[2])
        glBindVertexArray(self.light_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.light_vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices.tobytes(), GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        glDrawArrays(GL_LINES, 0, 2)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def draw_temp_loop(self, vertices, color):
        glUniform3f(glGetUniformLocation(self.shader_program, "u_pointColor"), color[0], color[1], color[2])
        glBindVertexArray(self.light_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.light_vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices.tobytes(), GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        glDrawArrays(GL_LINE_LOOP, 0, len(vertices))
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def get_orbit_ring_vertices(self):
        r = np.linalg.norm(self.light_pos_world)
        y = self.light_pos_world[1]
        h_radius = np.sqrt(max(r**2 - y**2, 0.0))
        
        angles = np.linspace(0, 2 * np.pi, 64, endpoint=False)
        xs = h_radius * np.sin(angles)
        zs = h_radius * np.cos(angles)
        ys = np.full_like(xs, y)
        
        vertices = np.stack([xs, ys, zs], axis=1).astype(np.float32)
        return vertices

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        self.update()

    # --- Interaction Events ---
    def mousePressEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            self.last_mouse_pos = event.position()

    def mouseMoveEvent(self, event):
        if self.last_mouse_pos is None:
            return
            
        current_pos = event.position()
        delta = current_pos - self.last_mouse_pos
        self.last_mouse_pos = current_pos
        
        if event.buttons() & Qt.LeftButton:
            # Orbit rotation
            self.yaw += delta.x() * 0.4
            self.pitch += delta.y() * 0.4
            
            # Constrain pitch (no vertical flips)
            self.pitch = max(-89.0, min(89.0, self.pitch))
            self.camera_changed.emit(self.yaw, self.pitch, self.distance)
            
        elif event.buttons() & Qt.RightButton:
            # Pan (shift model target)
            factor = 0.003 * self.distance
            self.pan_x += delta.x() * factor
            self.pan_y -= delta.y() * factor
            
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        # Zoom camera distance
        zoom_speed = 0.05 * self.distance
        if delta > 0:
            self.distance = max(0.2, self.distance - zoom_speed)
        else:
            self.distance = min(20.0, self.distance + zoom_speed)
            
        self.camera_changed.emit(self.yaw, self.pitch, self.distance)
        self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Point Cloud Sphere Renderer")
        self.resize(1100, 750)
        self.setStyleSheet(DARK_STYLE)
        
        # Load and process coordinate data
        self.points, self.center, self.scale = self.load_point_cloud("points.json")
        self.all_points = self.points.copy()
        self.shuffled_indices = np.random.permutation(len(self.all_points))
        
        # Central structural layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Construct layout parts
        self.create_sidebar()
        
        # OpenGL Widget Setup
        self.gl_widget = PointCloudWidget(self)
        self.gl_widget.scale = self.scale
        self.gl_widget.set_points(self.points)
        self.gl_widget.camera_changed.connect(self.sync_camera_sliders)
        
        # Assemble split interface
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.gl_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([320, 780])
        
        main_layout.addWidget(splitter)
        
        # Initialize UI slider positions
        self.reset_to_defaults()

    def load_point_cloud(self, filepath):
        """Loads points from JSON and normalizes coordinates around the origin."""
        if not os.path.exists(filepath):
            print(f"Error: {filepath} not found. Creating random dataset for demonstration.")
            # Fallback data if file is missing
            dummy = np.random.normal(0.0, 0.4, (2000, 3))
            return dummy, np.zeros(3), 1.0
            
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            raw_points = np.array(data['points'], dtype=np.float32)
            
            # Align center of mass to origin
            center = np.mean(raw_points, axis=0)
            centered_points = raw_points - center
            
            # Scale coordinates calculation (Removed scaling, translation only)
            max_dist = np.max(np.linalg.norm(centered_points, axis=1))
            if max_dist <= 0:
                max_dist = 1.0
                
            print(f"Successfully loaded {len(raw_points)} points.")
            return centered_points, center, max_dist
        except Exception as e:
            print(f"Error loading points file: {e}")
            dummy = np.random.normal(0.0, 0.4, (2000, 3))
            return dummy, np.zeros(3), 1.0

    def create_sidebar(self):
        """Creates the dark sidebar containing settings panels."""
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebarFrame")
        self.sidebar.setMinimumWidth(280)
        self.sidebar.setMaximumWidth(360)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(10)
        
        # App Title headers
        title = QLabel("ILLUSION 3D")
        title.setObjectName("titleLabel")
        subtitle = QLabel("3D Point Cloud Shader Tool")
        subtitle.setObjectName("subtitleLabel")
        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)
        
        # Group 1: Point Settings
        point_group = QGroupBox("Point Cloud Settings")
        point_layout = QGridLayout(point_group)
        point_layout.setSpacing(8)
        
        # Size Control
        point_layout.addWidget(QLabel("Sphere Size:"), 0, 0)
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0.001 * self.scale, 0.200 * self.scale)
        self.size_spin.setSingleStep(0.005 * self.scale)
        self.size_spin.setDecimals(4)
        self.size_spin.valueChanged.connect(self.on_size_spin_changed)
        point_layout.addWidget(self.size_spin, 0, 1)
        
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 200) # multiplier map
        self.size_slider.valueChanged.connect(self.on_size_slider_changed)
        point_layout.addWidget(self.size_slider, 1, 0, 1, 2)
        
        # Color Controls
        point_layout.addWidget(QLabel("Hue:"), 2, 0)
        self.hue_spin = QDoubleSpinBox()
        self.hue_spin.setRange(0.0, 1.0)
        self.hue_spin.setSingleStep(0.05)
        self.hue_spin.valueChanged.connect(self.on_color_changed)
        point_layout.addWidget(self.hue_spin, 2, 1)
        
        self.hue_slider = QSlider(Qt.Horizontal)
        self.hue_slider.setRange(0, 100)
        self.hue_slider.valueChanged.connect(self.on_hue_slider_changed)
        point_layout.addWidget(self.hue_slider, 3, 0, 3, 2)
        
        # Sample Count Controls
        point_layout.addWidget(QLabel("Sample Count:"), 6, 0)
        self.sample_spin = QSpinBox()
        self.sample_spin.setRange(100, len(self.all_points))
        self.sample_spin.setSingleStep(500)
        self.sample_spin.valueChanged.connect(self.on_sample_spin_changed)
        point_layout.addWidget(self.sample_spin, 6, 1)
        
        self.sample_slider = QSlider(Qt.Horizontal)
        self.sample_slider.setRange(100, len(self.all_points))
        self.sample_slider.valueChanged.connect(self.on_sample_slider_changed)
        point_layout.addWidget(self.sample_slider, 7, 0, 1, 2)
        
        sidebar_layout.addWidget(point_group)
        
        # Group 2: Light Position (Spherical coordinates mapping for orbit rotation)
        light_group = QGroupBox("Light Position (Orbit)")
        light_layout = QGridLayout(light_group)
        light_layout.setSpacing(8)
        
        # Light Distance (Radius)
        light_layout.addWidget(QLabel("Light Distance:"), 0, 0)
        self.light_dist_spin = QDoubleSpinBox()
        self.light_dist_spin.setRange(0.1 * self.scale, 10.0 * self.scale)
        self.light_dist_spin.setSingleStep(0.2 * self.scale)
        self.light_dist_spin.valueChanged.connect(self.update_light_position)
        light_layout.addWidget(self.light_dist_spin, 0, 1)
        
        self.light_dist_slider = QSlider(Qt.Horizontal)
        self.light_dist_slider.setRange(10, 1000) # relative scaling map
        self.light_dist_slider.valueChanged.connect(self.on_light_dist_slider_changed)
        light_layout.addWidget(self.light_dist_slider, 1, 0, 1, 2)
        
        # Light Azimuth (Horizontal angle)
        light_layout.addWidget(QLabel("Azimuth (Horiz):"), 2, 0)
        self.light_azimuth_spin = QDoubleSpinBox()
        self.light_azimuth_spin.setRange(-180.0, 180.0)
        self.light_azimuth_spin.setSingleStep(5.0)
        self.light_azimuth_spin.valueChanged.connect(self.update_light_position)
        light_layout.addWidget(self.light_azimuth_spin, 2, 1)
        
        self.light_azimuth_slider = QSlider(Qt.Horizontal)
        self.light_azimuth_slider.setRange(-180, 180)
        self.light_azimuth_slider.valueChanged.connect(self.on_light_azimuth_slider_changed)
        light_layout.addWidget(self.light_azimuth_slider, 3, 0, 1, 2)
        
        # Light Elevation (Vertical angle)
        light_layout.addWidget(QLabel("Elevation (Vert):"), 4, 0)
        self.light_elevation_spin = QDoubleSpinBox()
        self.light_elevation_spin.setRange(-90.0, 90.0)
        self.light_elevation_spin.setSingleStep(5.0)
        self.light_elevation_spin.valueChanged.connect(self.update_light_position)
        light_layout.addWidget(self.light_elevation_spin, 4, 1)
        
        self.light_elevation_slider = QSlider(Qt.Horizontal)
        self.light_elevation_slider.setRange(-90, 90)
        self.light_elevation_slider.valueChanged.connect(self.on_light_elevation_slider_changed)
        light_layout.addWidget(self.light_elevation_slider, 5, 0, 1, 2)
        
        sidebar_layout.addWidget(light_group)
        
        # Group 3: Camera Orbit Settings
        camera_group = QGroupBox("Camera Angles & Zoom")
        camera_layout = QGridLayout(camera_group)
        camera_layout.setSpacing(8)
        
        # Camera Yaw (Yaw = Yaw Angle Slider)
        camera_layout.addWidget(QLabel("Yaw (Rotate H):"), 0, 0)
        self.yaw_spin = QDoubleSpinBox()
        self.yaw_spin.setRange(-180.0, 180.0)
        self.yaw_spin.setSingleStep(5.0)
        self.yaw_spin.valueChanged.connect(self.update_camera_from_ui)
        camera_layout.addWidget(self.yaw_spin, 0, 1)
        
        self.yaw_slider = QSlider(Qt.Horizontal)
        self.yaw_slider.setRange(-180, 180)
        self.yaw_slider.valueChanged.connect(self.on_yaw_slider_changed)
        camera_layout.addWidget(self.yaw_slider, 1, 0, 1, 2)
        
        # Camera Pitch
        camera_layout.addWidget(QLabel("Pitch (Rotate V):"), 2, 0)
        self.pitch_spin = QDoubleSpinBox()
        self.pitch_spin.setRange(-89.0, 89.0)
        self.pitch_spin.setSingleStep(5.0)
        self.pitch_spin.valueChanged.connect(self.update_camera_from_ui)
        camera_layout.addWidget(self.pitch_spin, 2, 1)
        
        self.pitch_slider = QSlider(Qt.Horizontal)
        self.pitch_slider.setRange(-89, 89)
        self.pitch_slider.valueChanged.connect(self.on_pitch_slider_changed)
        camera_layout.addWidget(self.pitch_slider, 3, 0, 1, 2)
        
        # Camera Zoom / Distance
        camera_layout.addWidget(QLabel("Camera Distance:"), 4, 0)
        self.dist_spin = QDoubleSpinBox()
        self.dist_spin.setRange(0.1 * self.scale, 15.0 * self.scale)
        self.dist_spin.setSingleStep(0.2 * self.scale)
        self.dist_spin.valueChanged.connect(self.update_camera_from_ui)
        camera_layout.addWidget(self.dist_spin, 4, 1)
        
        self.dist_slider = QSlider(Qt.Horizontal)
        self.dist_slider.setRange(10, 1500) # scale multiplier mapping
        self.dist_slider.valueChanged.connect(self.on_dist_slider_changed)
        camera_layout.addWidget(self.dist_slider, 5, 0, 1, 2)
        
        sidebar_layout.addWidget(camera_group)
        
        # Data Info card
        info_group = QGroupBox("Dataset Details")
        info_layout = QVBoxLayout(info_group)
        self.points_label = QLabel(f"Total Points: {len(self.points)}")
        self.center_label = QLabel(f"Center: ({self.center[0]:.2f}, {self.center[1]:.2f}, {self.center[2]:.2f})")
        info_layout.addWidget(self.points_label)
        info_layout.addWidget(self.center_label)
        sidebar_layout.addWidget(info_group)
        
        # Reset control buttons at bottom
        sidebar_layout.addStretch(1)
        
        self.reset_btn = QPushButton("Reset View")
        self.reset_btn.setObjectName("resetBtn")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        sidebar_layout.addWidget(self.reset_btn)

    # --- Synchronize Sliders and SpinBoxes ---
    # 1. Sphere Size Controls
    def on_size_spin_changed(self, val):
        divisor = self.scale if self.scale > 0 else 1.0
        slider_val = int((val / divisor) * 1000)
        if self.size_slider.value() != slider_val:
            self.size_slider.setValue(slider_val)
        self.gl_widget.point_size = val
        self.gl_widget.update()

    def on_size_slider_changed(self, val):
        real_val = (val / 1000.0) * self.scale
        if abs(self.size_spin.value() - real_val) > 0.0001:
            self.size_spin.setValue(real_val)

    # 2. Point Color Controls (Hue)
    def on_color_changed(self, h_val):
        if self.hue_slider.value() != int(h_val * 100):
            self.hue_slider.setValue(int(h_val * 100))
            
        # Convert HSV (Hue, 1.0, 1.0) to RGB for modern styling
        r, g, b = self.hsv_to_rgb(h_val, 0.75, 0.95)
        self.gl_widget.point_color = np.array([r, g, b], dtype=np.float32)
        self.gl_widget.update()

    def on_hue_slider_changed(self, val):
        real_val = val / 100.0
        if abs(self.hue_spin.value() - real_val) > 0.001:
            self.hue_spin.setValue(real_val)

    def hsv_to_rgb(self, h, s, v):
        """Converts HSV scale (0-1) to RGB (0-1)."""
        if s == 0.0: return v, v, v
        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i %= 6
        if i == 0: return v, t, p
        if i == 1: return q, v, p
        if i == 2: return p, v, t
        if i == 3: return p, q, v
        if i == 4: return t, p, v
        if i == 5: return v, p, q

    # 3. Light Position Controls (Spherical Orbit mapping)
    def update_light_position(self):
        r = self.light_dist_spin.value()
        azimuth = np.radians(self.light_azimuth_spin.value())
        elevation = np.radians(self.light_elevation_spin.value())
        
        # Spherical coordinate conversion to cartesian
        x = r * np.cos(elevation) * np.sin(azimuth)
        y = r * np.sin(elevation)
        z = r * np.cos(elevation) * np.cos(azimuth)
        
        # Block signals temporarily to prevent loopback trigger
        self.light_dist_slider.blockSignals(True)
        self.light_azimuth_slider.blockSignals(True)
        self.light_elevation_slider.blockSignals(True)
        
        divisor = self.scale if self.scale > 0 else 1.0
        self.light_dist_slider.setValue(int((r / divisor) * 100))
        self.light_azimuth_slider.setValue(int(self.light_azimuth_spin.value()))
        self.light_elevation_slider.setValue(int(self.light_elevation_spin.value()))
        
        self.light_dist_slider.blockSignals(False)
        self.light_azimuth_slider.blockSignals(False)
        self.light_elevation_slider.blockSignals(False)
        
        self.gl_widget.light_pos_world = np.array([x, y, z], dtype=np.float32)
        self.gl_widget.update()

    def on_light_dist_slider_changed(self, val):
        self.light_dist_spin.setValue((val / 100.0) * self.scale)

    def on_light_azimuth_slider_changed(self, val):
        self.light_azimuth_spin.setValue(float(val))

    def on_light_elevation_slider_changed(self, val):
        self.light_elevation_spin.setValue(float(val))

    # 4. Camera Angle and Zoom Controls
    def update_camera_from_ui(self):
        self.gl_widget.yaw = self.yaw_spin.value()
        self.gl_widget.pitch = self.pitch_spin.value()
        self.gl_widget.distance = self.dist_spin.value()
        
        # Block signals temporarily to prevent circular feedback loops
        self.yaw_slider.blockSignals(True)
        self.pitch_slider.blockSignals(True)
        self.dist_slider.blockSignals(True)
        
        divisor = self.scale if self.scale > 0 else 1.0
        self.yaw_slider.setValue(int(self.gl_widget.yaw))
        self.pitch_slider.setValue(int(self.gl_widget.pitch))
        self.dist_slider.setValue(int((self.gl_widget.distance / divisor) * 100))
        
        self.yaw_slider.blockSignals(False)
        self.pitch_slider.blockSignals(False)
        self.dist_slider.blockSignals(False)
        
        self.gl_widget.update()

    def on_yaw_slider_changed(self, val):
        self.yaw_spin.setValue(float(val))

    def on_pitch_slider_changed(self, val):
        self.pitch_spin.setValue(float(val))

    def on_dist_slider_changed(self, val):
        self.dist_spin.setValue((val / 100.0) * self.scale)

    @Slot(float, float, float)
    def sync_camera_sliders(self, yaw, pitch, distance):
        """Called when user manipulates camera via 3D viewport drag/zoom."""
        self.yaw_spin.blockSignals(True)
        self.pitch_spin.blockSignals(True)
        self.dist_spin.blockSignals(True)
        
        self.yaw_slider.blockSignals(True)
        self.pitch_slider.blockSignals(True)
        self.dist_slider.blockSignals(True)
        
        # Normalise yaw to [-180, 180] for readable UI
        norm_yaw = (yaw + 180) % 360 - 180
        
        self.yaw_spin.setValue(norm_yaw)
        self.pitch_spin.setValue(pitch)
        self.dist_spin.setValue(distance)
        
        divisor = self.scale if self.scale > 0 else 1.0
        self.yaw_slider.setValue(int(norm_yaw))
        self.pitch_slider.setValue(int(pitch))
        self.dist_slider.setValue(int((distance / divisor) * 100))
        
        self.yaw_spin.blockSignals(False)
        self.pitch_spin.blockSignals(False)
        self.dist_spin.blockSignals(False)
        
        self.yaw_slider.blockSignals(False)
        self.pitch_slider.blockSignals(False)
        self.dist_slider.blockSignals(False)

    # 5. Point Random Sampling Controls
    def on_sample_spin_changed(self, val):
        if self.sample_slider.value() != val:
            self.sample_slider.setValue(val)
        self.apply_sampling()

    def on_sample_slider_changed(self, val):
        if self.sample_spin.value() != val:
            self.sample_spin.setValue(val)
        self.apply_sampling()

    def apply_sampling(self):
        count = self.sample_spin.value()
        indices = self.shuffled_indices[:count]
        self.points = self.all_points[indices]
        self.gl_widget.set_points(self.points)
        self.points_label.setText(f"Total Points: {len(self.points)}")

    def reset_to_defaults(self):
        """Resets all widget sliders back to defaults."""
        self.size_spin.setValue(0.025 * self.scale)
        self.hue_spin.setValue(0.55) # Cyan-blue base color
        
        if hasattr(self, 'all_points'):
            self.sample_spin.setValue(len(self.all_points))
            
        self.light_dist_spin.setValue(2.5 * self.scale)
        self.light_azimuth_spin.setValue(45.0)
        self.light_elevation_spin.setValue(35.0)
        
        self.gl_widget.pan_x = 0.0
        self.gl_widget.pan_y = 0.0
        
        self.yaw_spin.setValue(-45.0)
        self.pitch_spin.setValue(30.0)
        self.dist_spin.setValue(2.5 * self.scale)
        
        self.update_camera_from_ui()
        self.update_light_position()


if __name__ == "__main__":
    # Request clean OpenGL 3.3 Context Profile
    gl_format = QSurfaceFormat()
    gl_format.setDepthBufferSize(24)
    gl_format.setStencilBufferSize(8)
    gl_format.setVersion(3, 3)
    gl_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    QSurfaceFormat.setDefaultFormat(gl_format)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
