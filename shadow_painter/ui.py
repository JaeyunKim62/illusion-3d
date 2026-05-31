import os
import sys
import numpy as np
from PySide6.QtCore import Qt, Signal, Slot, QRect, QPointF, QPoint, QRectF, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QBrush, QPolygonF, QPixmap, QVector3D, QRadialGradient
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QScrollArea, QFrame, QGroupBox,
    QPushButton, QComboBox, QLabel, QSlider, QCheckBox, QFileDialog, QMessageBox
)
from PySide6.Qt3DExtras import Qt3DExtras

from shadow_painter.image_processor import (
    load_and_preprocess_image,
    generate_mask,
    generate_voronoi_pieces,
    generate_default_silhouette
)
from shadow_painter.geometry_engine import export_to_obj, export_to_svg
from shadow_painter.renderer import StainedGlassRenderer


class SliderGroup(QWidget):
    """
    Custom widget grouping a Label, QSlider, and value Label.
    Supports floating point mapping.
    """
    valueChanged = Signal(float)
    
    def __init__(self, title, min_val, max_val, default_val, scale=100.0, format_str="{:.2f}", parent=None):
        super().__init__(parent)
        self.scale = scale
        self.format_str = format_str
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)
        
        # Label layout
        lbl_layout = QHBoxLayout()
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-weight: bold; color: #a5a5b5;")
        self.lbl_val = QLabel("")
        self.lbl_val.setStyleSheet("color: #00f5d4; font-weight: bold;")
        lbl_layout.addWidget(self.lbl_title)
        lbl_layout.addStretch()
        lbl_layout.addWidget(self.lbl_val)
        layout.addLayout(lbl_layout)
        
        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_val * scale), int(max_val * scale))
        self.slider.setValue(int(default_val * scale))
        self.slider.setSingleStep(1)
        self.slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.slider)
        
        self._on_value_changed(self.slider.value())
        
    def _on_value_changed(self, val):
        float_val = val / self.scale
        self.lbl_val.setText(self.format_str.format(float_val))
        self.valueChanged.emit(float_val)
        
    def value(self):
        return self.slider.value() / self.scale
        
    def setValue(self, val):
        self.slider.blockSignals(True)
        self.slider.setValue(int(val * self.scale))
        self.lbl_val.setText(self.format_str.format(val))
        self.slider.blockSignals(False)


class AngleGizmoWidget(QWidget):
    """
    Custom widget rendering a single 3D sphere with two orthogonal circles (Yaw and Pitch rings)
    to visually control the camera view direction.
    """
    anglesChanged = Signal(float, float) # azimuth, elevation (in radians)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.azimuth = 0.0 # yaw (horizontal)
        self.elevation = 0.0 # pitch (vertical)
        
        self.setMinimumSize(280, 200)
        self.setMaximumSize(300, 220)
        self.active_handle = None # 'yaw' or 'pitch'
        
    def set_angles(self, azimuth, elevation):
        self.azimuth = azimuth
        self.elevation = elevation
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dark widget container background
        painter.fillRect(self.rect(), QColor("#1e1e24"))
        
        w = self.width()
        h = self.height()
        R_s = 60.0 # Sphere radius
        
        # Center of sphere
        cx = w // 2
        cy = h // 2 - 10
        
        # 3D projection parameters (camera viewing angles for the gizmo sphere)
        alpha = np.radians(20.0)  # Tilt up/down
        beta = np.radians(-30.0)  # Tilt left/right
        
        # 1. Draw Shaded Sphere Background (3D illusion)
        gradient = QRadialGradient(QPointF(cx, cy), R_s)
        gradient.setColorAt(0.0, QColor(45, 45, 55))
        gradient.setColorAt(0.8, QColor(25, 25, 32))
        gradient.setColorAt(1.0, QColor(15, 15, 18))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(70, 70, 80), 1))
        painter.drawEllipse(QPointF(cx, cy), R_s, R_s)
        
        # Helper to project a 3D point (x, y, z) on the sphere
        def project_point_3d(x, y, z):
            # Rotate around Y axis by beta
            cos_b, sin_b = np.cos(beta), np.sin(beta)
            x_p = x * cos_b + z * sin_b
            z_p = -x * sin_b + z * cos_b
            
            # Rotate around X axis by alpha
            cos_a, sin_a = np.cos(alpha), np.sin(alpha)
            y_d = y * cos_a - z_p * sin_a
            z_d = y * sin_a + z_p * cos_a
            
            return x_p, y_d, z_d

        # Helper to draw a circle of line segments, checking depth for dashed/solid rendering
        def draw_projected_circle(points_3d, color_front, color_back):
            N = len(points_3d)
            proj_pts = []
            depths = []
            for pt in points_3d:
                xp, yd, zd = project_point_3d(pt[0], pt[1], pt[2])
                proj_pts.append(QPointF(cx + xp, cy + yd))
                depths.append(zd)
                
            for i in range(N):
                i_next = (i + 1) % N
                z_avg = (depths[i] + depths[i_next]) / 2.0
                
                pen = QPen()
                if z_avg <= 0: # Front hemisphere (closer to camera)
                    pen.setColor(color_front)
                    pen.setWidth(2)
                    pen.setStyle(Qt.PenStyle.SolidLine)
                else: # Back hemisphere
                    pen.setColor(color_back)
                    pen.setWidth(1)
                    pen.setStyle(Qt.PenStyle.DotLine)
                    
                painter.setPen(pen)
                painter.drawLine(proj_pts[i], proj_pts[i_next])
                
        # 2. Draw Yaw Ring (Horizontal circle in XZ plane)
        angles = np.linspace(0, 2 * np.pi, 72)
        yaw_pts = np.zeros((72, 3))
        yaw_pts[:, 0] = R_s * np.sin(angles)
        yaw_pts[:, 1] = 0.0
        yaw_pts[:, 2] = R_s * np.cos(angles)
        draw_projected_circle(yaw_pts, QColor("#3a86ff"), QColor(58, 134, 255, 60))
        
        # 3. Draw Pitch Ring (Vertical circle in YZ plane)
        pitch_pts = np.zeros((72, 3))
        pitch_pts[:, 0] = 0.0
        pitch_pts[:, 1] = R_s * np.sin(angles)
        pitch_pts[:, 2] = R_s * np.cos(angles)
        draw_projected_circle(pitch_pts, QColor("#ff007f"), QColor(255, 0, 127, 60))
        
        # 4. Project and Draw Yaw Handle
        y_hx, y_hy, y_hz = project_point_3d(R_s * np.sin(self.azimuth), 0.0, R_s * np.cos(self.azimuth))
        yaw_handle_pos = QPointF(cx + y_hx, cy + y_hy)
        
        painter.setPen(QPen(QColor("#00f5d4"), 2))
        painter.setBrush(QBrush(QColor("#00f5d4")))
        painter.drawEllipse(yaw_handle_pos, 5, 5)
        
        # 5. Project and Draw Pitch Handle
        p_hx, p_hy, p_hz = project_point_3d(0.0, R_s * np.sin(self.elevation), R_s * np.cos(self.elevation))
        pitch_handle_pos = QPointF(cx + p_hx, cy + p_hy)
        
        painter.setPen(QPen(QColor("#00f5d4"), 2))
        painter.setBrush(QBrush(QColor("#00f5d4")))
        painter.drawEllipse(pitch_handle_pos, 5, 5)
        
        # Store handle positions for mouse hit testing
        self._yaw_handle_pos = yaw_handle_pos
        self._pitch_handle_pos = pitch_handle_pos
        
        # 6. Draw Text Info
        painter.setFont(self.font())
        painter.setPen(QColor("#a5a5b5"))
        painter.drawText(QRect(10, h - 35, w - 20, 16), Qt.AlignmentFlag.AlignCenter, 
                         f"Yaw (Blue): {np.degrees(self.azimuth):.1f}° | Pitch (Pink): {np.degrees(self.elevation):.1f}°")
        painter.drawText(QRect(10, h - 20, w - 20, 16), Qt.AlignmentFlag.AlignCenter, 
                         "Drag handles to rotate camera view")

    def mousePressEvent(self, event):
        pos = event.position()
        dist_yaw = np.hypot(pos.x() - self._yaw_handle_pos.x(), pos.y() - self._yaw_handle_pos.y())
        dist_pitch = np.hypot(pos.x() - self._pitch_handle_pos.x(), pos.y() - self._pitch_handle_pos.y())
        
        if dist_yaw < 18 and dist_yaw < dist_pitch:
            self.active_handle = 'yaw'
        elif dist_pitch < 18:
            self.active_handle = 'pitch'
        else:
            self.active_handle = None
            
    def mouseMoveEvent(self, event):
        if not self.active_handle:
            return
            
        w = self.width()
        h = self.height()
        cx = w // 2
        cy = h // 2 - 10
        R_s = 60.0
        
        pos = event.position()
        mx = pos.x() - cx
        my = pos.y() - cy
        
        # 3D projection parameters (same as paintEvent)
        alpha = np.radians(20.0)
        beta = np.radians(-30.0)
        
        if self.active_handle == 'yaw':
            # Optimize to find the yaw (azimuth) angle that minimizes distance to mouse
            candidates = np.linspace(-np.pi, np.pi, 360)
            xs = R_s * np.sin(candidates)
            zs = R_s * np.cos(candidates)
            
            cos_b, sin_b = np.cos(beta), np.sin(beta)
            xp = xs * cos_b + zs * sin_b
            zp = -xs * sin_b + zs * cos_b
            
            cos_a, sin_a = np.cos(alpha), np.sin(alpha)
            yd = -zp * sin_a
            
            dists = (xp - mx)**2 + (yd - my)**2
            best_idx = np.argmin(dists)
            self.azimuth = candidates[best_idx]
        else:
            # Optimize to find the pitch (elevation) angle in [-pi/2, pi/2]
            candidates = np.linspace(-np.pi/2, np.pi/2, 180)
            ys = R_s * np.sin(candidates)
            zs = R_s * np.cos(candidates)
            
            cos_b, sin_b = np.cos(beta), np.sin(beta)
            xp = zs * sin_b
            zp = zs * cos_b
            
            cos_a, sin_a = np.cos(alpha), np.sin(alpha)
            yd = ys * cos_a - zp * sin_a
            
            dists = (xp - mx)**2 + (yd - my)**2
            best_idx = np.argmin(dists)
            self.elevation = candidates[best_idx]
            
        self.anglesChanged.emit(self.azimuth, self.elevation)
        self.update()
        
    def mouseReleaseEvent(self, event):
        self.active_handle = None
        self.update()


class StainedGlassPreviewWidget(QWidget):
    """
    Renders the 2D loaded image and overlays the Voronoi segmentation wireframe.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.img_rgb = None
        self.pieces = []
        self.setMinimumSize(200, 200)
        
    def set_data(self, img_rgb, pieces):
        self.img_rgb = img_rgb.copy() if img_rgb is not None else None
        self.pieces = pieces
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw dark canvas background
        painter.fillRect(self.rect(), QColor("#121214"))
        
        if self.img_rgb is None:
            painter.setPen(QColor("#888888"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Image Loaded")
            return
            
        h_img, w_img = self.img_rgb.shape[:2]
        aspect_img = w_img / h_img
        aspect_widget = self.width() / self.height()
        
        if aspect_img > aspect_widget:
            w_draw = self.width()
            h_draw = int(w_draw / aspect_img)
        else:
            h_draw = self.height()
            w_draw = int(h_draw * aspect_img)
            
        x_draw = (self.width() - w_draw) // 2
        y_draw = (self.height() - h_draw) // 2
        
        # Draw background image
        # Using deep copy .copy() to ensure numpy buffer stays alive in Qt
        qimg = QImage(self.img_rgb.data, w_img, h_img, 3 * w_img, QImage.Format.Format_RGB888).copy()
        draw_rect = QRect(x_draw, y_draw, w_draw, h_draw)
        painter.drawImage(draw_rect, qimg)
        
        # Draw outlines of segments
        scale_x = w_draw / w_img
        scale_y = h_draw / h_img
        
        pen = QPen(QColor(255, 255, 255, 120))
        pen.setWidth(1)
        painter.setPen(pen)
        
        for piece in self.pieces:
            cx, cy = piece['centroid']
            verts_abs = piece['vertices'] + [cx, cy]
            
            poly = QPolygonF()
            for pt in verts_abs:
                px = x_draw + pt[0] * scale_x
                py = y_draw + pt[1] * scale_y
                poly.append(QPointF(px, py))
                
            # Draw semi-transparent fill matching the piece's color
            r, g, b = piece['color']
            painter.setBrush(QBrush(QColor.fromRgbF(r, g, b, 0.15)))
            painter.drawPolygon(poly)


class MainWindow(QWidget):
    """
    Main application layout, managing sidebar controls, preview widget, and Qt 3D viewport.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stained Glass Shadow Art Generator")
        self.resize(1280, 800)
        self.setStyleSheet(self._get_stylesheet())
        
        # Pipeline state data
        self.img_rgb = None
        self.img_gray = None
        self.aspect = 1.0
        self.pieces = []
        self.t_list = []
        
        # Stained Glass & Screen Constants (removed from UI settings)
        self.glass_alpha_val = 0.6
        self.glass_thickness_val = 0.08
        self.tmin_val = 0.3
        self.tmax_val = 0.75
        self.screen_dist_val = 8.0
        self.screen_w_val = 8.0
        
        # Initialize UI layout
        self._init_ui()
        
        # Initialize 3D renderer inside Qt3DWindow
        self.view3D = Qt3DExtras.Qt3DWindow()
        self.view3D.defaultFrameGraph().setClearColor(QColor("#f5f5f7"))
        
        # Embed 3D View into layout
        container3D = QWidget.createWindowContainer(self.view3D)
        self.right_layout.addWidget(container3D)
        
        # Initialize renderer logic
        self.renderer = StainedGlassRenderer(self.view3D)
        self.renderer.set_glass_alpha(self.glass_alpha_val)
        
        # Connect camera view gizmo immediately to renderer camera
        self.light_gizmo.anglesChanged.connect(self._on_view_angles_changed)
        
        self.chk_light.stateChanged.connect(self._on_light_toggled)
        self.chk_shadows.stateChanged.connect(self._on_shadows_toggled)
        self.chk_rays.stateChanged.connect(self._on_rays_toggled)
        
        # Debounce timer for slider updates (prevents lags/crashes during rapid drags)
        self.reseg_timer = QTimer(self)
        self.reseg_timer.setSingleShot(True)
        self.reseg_timer.setInterval(180) # 180ms delay
        self.reseg_timer.timeout.connect(self._on_resegmentation_debounced)
        
        # Camera clamping timer to prevent rotating behind the screen
        self.cam_clamp_timer = QTimer(self)
        self.cam_clamp_timer.setInterval(16)
        self.cam_clamp_timer.timeout.connect(self._clamp_camera_position)
        self.cam_clamp_timer.start()
        
        # Load default scene
        self._load_default_scene()
        
    def _init_ui(self):
        # Main Layout split horizontally
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. Left Sidebar
        self.sidebar = QFrame(self)
        self.sidebar.setObjectName("sidebar")
        main_layout.addWidget(self.sidebar)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)
        
        # Scroll Area for sidebar widgets
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        sidebar_layout.addWidget(scroll)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(scroll_content)
        
        # --- Group A: Image Settings ---
        group_img = QGroupBox("Image Processing")
        group_img_layout = QVBoxLayout(group_img)
        group_img_layout.setSpacing(8)
        
        self.btn_load = QPushButton("Load Image File")
        self.btn_load.setObjectName("btn_load")
        self.btn_load.clicked.connect(self._on_load_image_clicked)
        group_img_layout.addWidget(self.btn_load)
        
        lbl_mode = QLabel("Segmentation Mask Mode:")
        group_img_layout.addWidget(lbl_mode)
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Silhouette (Auto-mask)", "Full Image Canvas"])
        self.combo_mode.currentIndexChanged.connect(self._trigger_resegmentation)
        group_img_layout.addWidget(self.combo_mode)
        
        self.slider_pieces = SliderGroup("Pieces Count", 20, 500, 50, scale=1.0, format_str="{:.0f}")
        self.slider_pieces.valueChanged.connect(self._trigger_resegmentation)
        group_img_layout.addWidget(self.slider_pieces)
        
        self.slider_jitter = SliderGroup("Detail Sensitivity", 0.0, 1.0, 0.65)
        self.slider_jitter.valueChanged.connect(self._trigger_resegmentation)
        group_img_layout.addWidget(self.slider_jitter)
        
        scroll_layout.addWidget(group_img)
        

        # --- Group C: Camera View Control ---
        group_view = QGroupBox("Camera View Control")
        group_view_layout = QVBoxLayout(group_view)
        group_view_layout.setSpacing(8)
        
        self.light_gizmo = AngleGizmoWidget(self)
        group_view_layout.addWidget(self.light_gizmo)
        
        self.chk_light = QCheckBox("Enable Spotlight (Light On)")
        self.chk_light.setChecked(True)
        group_view_layout.addWidget(self.chk_light)
        
        self.chk_shadows = QCheckBox("Render Colored Shadows")
        self.chk_shadows.setChecked(True)
        group_view_layout.addWidget(self.chk_shadows)
        
        self.chk_rays = QCheckBox("Show Light Rays (Projection)")
        self.chk_rays.setChecked(False)
        group_view_layout.addWidget(self.chk_rays)
        
        scroll_layout.addWidget(group_view)
        
        # --- Group B: Light Position Control ---
        group_light = QGroupBox("Light Position Control")
        group_light_layout = QVBoxLayout(group_light)
        group_light_layout.setSpacing(8)
        
        self.slider_light_x = SliderGroup("Horizontal Position (X)", -5.0, 5.0, 0.0, scale=100.0)
        self.slider_light_x.valueChanged.connect(self._on_light_x_changed)
        group_light_layout.addWidget(self.slider_light_x)
        
        scroll_layout.addWidget(group_light)
        
        # --- Group D: Actions ---
        group_act = QGroupBox("System Controls")
        group_act_layout = QVBoxLayout(group_act)
        group_act_layout.setSpacing(8)
        
        self.btn_random = QPushButton("Randomize Glass Depths")
        self.btn_random.setObjectName("btn_random")
        self.btn_random.clicked.connect(self._on_randomize_clicked)
        group_act_layout.addWidget(self.btn_random)
        
        self.btn_reset_cam = QPushButton("Reset View Angle")
        self.btn_reset_cam.clicked.connect(self._on_reset_cam_clicked)
        group_act_layout.addWidget(self.btn_reset_cam)
        
        self.btn_export_obj = QPushButton("Export OBJ (3D Mesh)")
        self.btn_export_obj.setObjectName("btn_export_obj")
        self.btn_export_obj.clicked.connect(self._on_export_obj_clicked)
        group_act_layout.addWidget(self.btn_export_obj)
        
        self.btn_export_svg = QPushButton("Export SVG (2D Template)")
        self.btn_export_svg.setObjectName("btn_export_svg")
        self.btn_export_svg.clicked.connect(self._on_export_svg_clicked)
        group_act_layout.addWidget(self.btn_export_svg)
        
        scroll_layout.addWidget(group_act)
        
        # --- Group E: 2D Layout Preview ---
        group_prev = QGroupBox("2D Vector Layout Preview")
        group_prev_layout = QVBoxLayout(group_prev)
        self.preview_widget = StainedGlassPreviewWidget()
        group_prev_layout.addWidget(self.preview_widget)
        scroll_layout.addWidget(group_prev)
        
        # 2. Right Viewport Area
        self.right_widget = QWidget(self)
        self.right_layout = QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.right_widget, 1) # Set stretch factor to 1 to occupy remaining space
        
    def _load_default_scene(self):
        """Loads default nup.png image on startup, falling back to programmatic mandala if missing."""
        # Get path of shadow_painter/nup.png relative to the parent directory of this module
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_img_path = os.path.join(base_dir, "shadow_painter", "nup.png")
        
        try:
            if os.path.exists(default_img_path):
                self.img_rgb, self.img_gray, self.aspect = load_and_preprocess_image(default_img_path)
            else:
                self.img_rgb, self.img_gray, self.aspect = generate_default_silhouette()
        except Exception:
            self.img_rgb, self.img_gray, self.aspect = generate_default_silhouette()
            
        self._segment_image()
        self._generate_t_list()
        self._rebuild_geometry()
        
    def _segment_image(self):
        """Runs segmentation pipeline to slice the image into Voronoi cells."""
        if self.img_rgb is None:
            return
            
        mode_idx = self.combo_mode.currentIndex()
        mode = "silhouette" if mode_idx == 0 else "full"
        
        mask = generate_mask(self.img_gray, mode)
        self.pieces = generate_voronoi_pieces(
            self.img_rgb, mask, int(self.slider_pieces.value()), self.slider_jitter.value()
        )
        
        # Update 2D preview
        self.preview_widget.set_data(self.img_rgb, self.pieces)
        
    def _generate_t_list(self):
        """Generates random depth factors t for each glass piece."""
        self.t_list = np.random.uniform(self.tmin_val, self.tmax_val, len(self.pieces))
        
    def _rebuild_geometry(self):
        """Rebuilds the Qt 3D scene geometry meshes."""
        if len(self.pieces) == 0:
            return
            
        h_img, w_img = self.img_rgb.shape[:2]
        
        self.renderer.rebuild_scene(
            pieces=self.pieces,
            image_w=w_img,
            image_h=h_img,
            screen_w=self.screen_w_val,
            z_screen=self.screen_dist_val,
            t_list=self.t_list,
            thickness=self.glass_thickness_val,
            glass_alpha=self.glass_alpha_val,
            show_shadows=self.chk_shadows.isChecked() and self.chk_light.isChecked()
        )
        
    @Slot(float)
    def _trigger_resegmentation(self, _=0.0):
        # Debounce the heavy K-means segmentation to prevent UI freezing
        self.reseg_timer.start()

    def _on_resegmentation_debounced(self):
        self._segment_image()
        self._generate_t_list()
        self._rebuild_geometry()
        
    @Slot(float)
    def _trigger_rebuild_geometry(self, _=0.0):
        self._rebuild_geometry()
        
    @Slot(float, float)
    def _on_view_angles_changed(self, yaw, pitch):
        self.renderer.set_camera_angles(yaw, pitch)
        
    @Slot(float)
    def _on_light_x_changed(self, val):
        if hasattr(self, 'renderer'):
            self.renderer.set_light_position(val, 0.0, 0.0)

    def _clamp_camera_position(self):
        if not hasattr(self, 'renderer') or not self.renderer.camera:
            return
            
        camera = self.renderer.camera
        pos = camera.position()
        center = camera.viewCenter()
        
        # Vector from center to camera
        vx = pos.x() - center.x()
        vy = pos.y() - center.y()
        vz = pos.z() - center.z()
        
        d = np.sqrt(vx*vx + vy*vy + vz*vz)
        if d < 0.1:
            return
            
        # 1. Extract current Yaw (azimuth) and Pitch (elevation)
        pitch = np.arcsin(np.clip(vy / d, -1.0, 1.0))
        yaw = np.arctan2(vx, -vz)
        
        # 2. Cone Clamp (Angle with -Z axis must be <= 75 degrees)
        theta_max = np.radians(75.0)
        cos_theta = -vz / d
        theta = np.arccos(np.clip(cos_theta, -1.0, 1.0))
        
        if theta > theta_max:
            # Reconstruct clamped coordinates on the cone boundary
            new_z_comp = d * np.cos(theta_max)
            new_r_lat = d * np.sin(theta_max)
            
            new_vz = -new_z_comp
            r_lat = np.sqrt(vx*vx + vy*vy)
            if r_lat > 0.001:
                new_vx = vx * (new_r_lat / r_lat)
                new_vy = vy * (new_r_lat / r_lat)
            else:
                new_vx = 0.0
                new_vy = 0.0
                
            new_pos = QVector3D(center.x() + new_vx, center.y() + new_vy, center.z() + new_vz)
            camera.setPosition(new_pos)
            pos = new_pos
            
            # Recalculate clamped angles
            vx = pos.x() - center.x()
            vy = pos.y() - center.y()
            vz = pos.z() - center.z()
            pitch = np.arcsin(np.clip(vy / d, -1.0, 1.0))
            yaw = np.arctan2(vx, -vz)
            
        # 3. Additionally enforce absolute Z limit to prevent penetrating the wall
        z_limit = self.renderer.z_screen - 1.2
        if pos.z() > z_limit:
            camera.setPosition(QVector3D(pos.x(), pos.y(), z_limit))
            # Recalculate angles if Z was clamped
            pos = camera.position()
            vx = pos.x() - center.x()
            vy = pos.y() - center.y()
            vz = pos.z() - center.z()
            d_clamped = np.sqrt(vx*vx + vy*vy + vz*vz)
            if d_clamped > 0.1:
                pitch = np.arcsin(np.clip(vy / d_clamped, -1.0, 1.0))
                yaw = np.arctan2(vx, -vz)
                
        # 4. Sync the Yaw/Pitch widget to match the 3D camera angles
        self.light_gizmo.blockSignals(True)
        self.light_gizmo.set_angles(yaw, pitch)
        self.light_gizmo.blockSignals(False)
        
    @Slot()
    def _on_randomize_clicked(self):
        self._generate_t_list()
        self._rebuild_geometry()
        
    @Slot(int)
    def _on_light_toggled(self, state):
        is_on = (state == 2)
        self.renderer.set_light_enabled(is_on)
        if not is_on:
            self.renderer.set_shadows_enabled(False)
        else:
            self.renderer.set_shadows_enabled(self.chk_shadows.isChecked())

    @Slot(int)
    def _on_shadows_toggled(self, state):
        if self.chk_light.isChecked():
            self.renderer.set_shadows_enabled(state == 2)
        else:
            self.renderer.set_shadows_enabled(False)
        
    @Slot(int)
    def _on_rays_toggled(self, state):
        self.renderer.set_rays_enabled(state == 2)
        
    @Slot()
    def _on_reset_cam_clicked(self):
        self.renderer.reset_camera()
        if hasattr(self, 'slider_light_x'):
            self.slider_light_x.setValue(0.0)
            self.renderer.set_light_position(0.0, 0.0, 0.0)
        
    @Slot()
    def _on_load_image_clicked(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Silhouette Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not filepath:
            return
            
        try:
            self.img_rgb, self.img_gray, self.aspect = load_and_preprocess_image(filepath)
            self._segment_image()
            self._generate_t_list()
            self._rebuild_geometry()
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Image", f"Failed to load and process image:\n{str(e)}")
            
    @Slot()
    def _on_export_obj_clicked(self):
        if len(self.pieces) == 0:
            QMessageBox.warning(self, "No Geometry", "No stained glass geometry to export.")
            return
            
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export 3D Model", "stained_glass_art.obj", "Wavefront OBJ (*.obj)"
        )
        if not filepath:
            return
            
        try:
            h_img, w_img = self.img_rgb.shape[:2]
            success = export_to_obj(
                filepath=filepath,
                pieces=self.pieces,
                image_w=w_img,
                image_h=h_img,
                screen_w=self.screen_w_val,
                screen_h=self.screen_w_val * (h_img / w_img),
                z_screen=self.screen_dist_val,
                t_list=self.t_list,
                thickness=self.glass_thickness_val,
                L_ref=(0, 0, 0)
            )
            if success:
                QMessageBox.information(self, "Export Successful", f"3D Mesh successfully exported to:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred during OBJ export:\n{str(e)}")
            
    @Slot()
    def _on_export_svg_clicked(self):
        if len(self.pieces) == 0:
            QMessageBox.warning(self, "No Layout", "No stained glass layout to export.")
            return
            
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export 2D Layout", "stained_glass_template.svg", "Scalable Vector Graphics (*.svg)"
        )
        if not filepath:
            return
            
        try:
            h_img, w_img = self.img_rgb.shape[:2]
            success = export_to_svg(filepath, self.pieces, w_img, h_img)
            if success:
                QMessageBox.information(self, "Export Successful", f"2D Layout successfully exported to:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred during SVG export:\n{str(e)}")
            
    def _get_stylesheet(self):
        return """
        QWidget {
            background-color: #121214;
            color: #e0e0e0;
            font-family: '.AppleSystemUIFont', 'Segoe UI', Helvetica, sans-serif;
            font-size: 11px;
        }
        
        QLabel, QCheckBox {
            background-color: transparent;
        }
        
        QFrame#sidebar {
            background-color: #18181c;
            border-right: 1px solid #282830;
            min-width: 320px;
            max-width: 320px;
        }
        
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        
        QGroupBox {
            border: 1px solid #2d2d35;
            border-radius: 8px;
            margin-top: 14px;
            padding-top: 16px;
            padding-bottom: 8px;
            padding-left: 8px;
            padding-right: 8px;
            background-color: #1e1e24;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 2px 6px;
            color: #ffffff;
            font-weight: bold;
            font-size: 11.5px;
            background-color: #1e1e24;
            border-radius: 4px;
        }
        
        QPushButton {
            background-color: #3a86ff;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 8px 12px;
            font-weight: bold;
            font-size: 11px;
        }
        
        QPushButton:hover {
            background-color: #5596ff;
        }
        
        QPushButton:pressed {
            background-color: #2675ec;
        }
        
        QPushButton#btn_load {
            background-color: #06d6a0;
            color: #121214;
        }
        QPushButton#btn_load:hover {
            background-color: #2cfcd0;
        }
        
        QPushButton#btn_random {
            background-color: #ff007f;
        }
        QPushButton#btn_random:hover {
            background-color: #ff3399;
        }
        
        QPushButton#btn_export_obj, QPushButton#btn_export_svg {
            background-color: #495057;
        }
        QPushButton#btn_export_obj:hover, QPushButton#btn_export_svg:hover {
            background-color: #6c757d;
        }
        
        QComboBox {
            border: 1px solid #2d2d35;
            border-radius: 5px;
            padding: 6px;
            background-color: #121214;
            color: white;
            combobox-popup: 0;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        
        QSlider::groove:horizontal {
            border: none;
            height: 4px;
            background: #2a2a30;
            border-radius: 2px;
        }
        
        QSlider::handle:horizontal {
            background: #00f5d4;
            border: none;
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
        
        QSlider::handle:horizontal:hover {
            background: #33ffd1;
        }
        
        QCheckBox {
            color: #d1d1d6;
            spacing: 8px;
            font-weight: bold;
        }
        
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #3c3c46;
            border-radius: 4px;
            background-color: #121214;
        }
        
        QCheckBox::indicator:checked {
            background-color: #00f5d4;
            border-color: #00f5d4;
        }
        
        QScrollBar:vertical {
            border: none;
            background: #18181c;
            width: 8px;
        }
        
        QScrollBar::handle:vertical {
            background: #2d2d35;
            min-height: 20px;
            border-radius: 4px;
        }
        
        QScrollBar::handle:vertical:hover {
            background: #444450;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        """
