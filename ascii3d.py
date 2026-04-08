#!/usr/bin/env python3
"""
ascii3d - Renderiza modelos 3D como ASCII art rotativo en la terminal.
Soporta: OBJ (wavefront), STL (ascii)
Uso: python3 ascii3d.py modelo.obj [--speed 0.05] [--wireframe] [--width 80]
"""

import sys
import os
import math
import time
import argparse
import signal
import tty
import termios
import select
import threading

# ─── Math helpers (sin numpy) ───

def vec3(x=0, y=0, z=0):
    return [float(x), float(y), float(z)]

def vec_add(a, b):
    return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]

def vec_sub(a, b):
    return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]

def vec_scale(v, s):
    return [v[0]*s, v[1]*s, v[2]*s]

def vec_dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def vec_cross(a, b):
    return [
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0]
    ]

def vec_len(v):
    return math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])

def vec_norm(v):
    l = vec_len(v)
    if l < 1e-10:
        return [0, 0, 0]
    return [v[0]/l, v[1]/l, v[2]/l]

def rotate_x(v, a):
    c, s = math.cos(a), math.sin(a)
    return [v[0], v[1]*c - v[2]*s, v[1]*s + v[2]*c]

def rotate_y(v, a):
    c, s = math.cos(a), math.sin(a)
    return [v[0]*c + v[2]*s, v[1], -v[0]*s + v[2]*c]

def rotate_z(v, a):
    c, s = math.cos(a), math.sin(a)
    return [v[0]*c - v[1]*s, v[0]*s + v[1]*c, v[2]]

# ─── Keyboard input handler ───

class KeyboardInput:
    """Non-blocking keyboard input using tty raw mode"""
    
    def __init__(self):
        self.old_settings = None
        self.running = False
        self.keys_pressed = set()
        self.lock = threading.Lock()
    
    def start(self):
        """Start listening for keyboard input"""
        try:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
            self.running = True
        except:
            self.running = False
    
    def stop(self):
        """Restore terminal settings"""
        self.running = False
        if self.old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
    
    def get_keys(self):
        """Get currently pressed keys (non-blocking)"""
        if not self.running:
            return set()
        
        keys = set()
        try:
            while select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if ch:
                    # Escape sequence (arrows)
                    if ch == '\x1b':
                        if select.select([sys.stdin], [], [], 0.01)[0]:
                            ch2 = sys.stdin.read(1)
                            if ch2 == '[':
                                ch3 = sys.stdin.read(1)
                                if ch3 == 'A': keys.add('up')
                                elif ch3 == 'B': keys.add('down')
                                elif ch3 == 'C': keys.add('right')
                                elif ch3 == 'D': keys.add('left')
                        else:
                            keys.add('escape')
                    # WASD
                    elif ch.lower() in 'wasd':
                        keys.add(ch.lower())
                    # Q to quit
                    elif ch.lower() == 'q':
                        keys.add('quit')
                    # Space
                    elif ch == ' ':
                        keys.add('space')
        except:
            pass
        
        return keys

# ─── Parsers ───

def parse_obj(filepath):
    """Parse Wavefront OBJ file"""
    verts = []
    faces = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if parts[0] == 'v' and len(parts) >= 4:
                verts.append(vec3(parts[1], parts[2], parts[3]))
            elif parts[0] == 'f':
                face_verts = []
                for p in parts[1:]:
                    # soporta f v, f v/vt, f v/vt/vn, f v//vn
                    idx = p.split('/')[0]
                    face_verts.append(int(idx) - 1)  # OBJ es 1-indexed
                faces.append(face_verts)
    return verts, faces

def parse_stl_ascii(filepath):
    """Parse ASCII STL file"""
    verts = []
    faces = []
    vert_map = {}
    current_verts = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('vertex'):
                parts = line.split()
                v = vec3(parts[1], parts[2], parts[3])
                # deduplicar vértices
                key = (round(v[0], 6), round(v[1], 6), round(v[2], 6))
                if key not in vert_map:
                    vert_map[key] = len(verts)
                    verts.append(v)
                current_verts.append(vert_map[key])
            elif line.startswith('endloop'):
                if len(current_verts) == 3:
                    faces.append(current_verts)
                current_verts = []

    return verts, faces

def parse_stl_binary(filepath):
    """Parse binary STL file"""
    import struct

    verts = []
    faces = []
    vert_map = {}

    with open(filepath, 'rb') as f:
        # Header (80 bytes)
        header = f.read(80)
        # Number of triangles (uint32)
        num_triangles = struct.unpack('<I', f.read(4))[0]

        for _ in range(num_triangles):
            # Normal (3 floats)
            normal = struct.unpack('<3f', f.read(12))
            # 3 vertices (3 floats each)
            triangle_verts = []
            for _ in range(3):
                data = f.read(12)
                if len(data) < 12:
                    break
                x, y, z = struct.unpack('<3f', data)
                v = vec3(x, y, z)
                key = (round(x, 4), round(y, 4), round(z, 4))
                if key not in vert_map:
                    vert_map[key] = len(verts)
                    verts.append(v)
                triangle_verts.append(vert_map[key])

            # Attribute byte count (2 bytes, usually 0)
            f.read(2)

            if len(triangle_verts) == 3:
                faces.append(triangle_verts)

    return verts, faces

def is_stl_binary(filepath):
    """Check if STL file is binary format"""
    with open(filepath, 'rb') as f:
        header = f.read(80)
        if len(header) < 80:
            return False
        # Try to read triangle count
        try:
            import struct
            num_tri = struct.unpack('<I', f.read(4))[0]
            # Binary STL size = 80 (header) + 4 (count) + num_tri * 50
            expected = 80 + 4 + num_tri * 50
            actual = os.path.getsize(filepath)
            return expected == actual
        except:
            return False

def load_model(filepath):
    """Auto-detect format and load model"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.obj':
        return parse_obj(filepath)
    elif ext == '.stl':
        if is_stl_binary(filepath):
            return parse_stl_binary(filepath)
        else:
            return parse_stl_ascii(filepath)
    else:
        # intentar OBJ primero
        try:
            return parse_obj(filepath)
        except:
            try:
                return parse_stl_ascii(filepath)
            except:
                return parse_stl_binary(filepath)

# ─── Model optimization ───

def decimate_model(verts, faces, max_faces=50000):
    """Reduce polygon count for large models"""
    if len(faces) <= max_faces:
        return verts, faces

    # Simple decimation: take every Nth face (deterministic)
    step = max(1, len(faces) // max_faces)
    new_faces = faces[::step]

    # Rebuild vertex list (only used verts)
    used_verts = set()
    for face in new_faces:
        used_verts.update(face)

    old_to_new = {}
    new_verts = []
    for old_idx in sorted(used_verts):
        old_to_new[old_idx] = len(new_verts)
        new_verts.append(verts[old_idx])

    # Remap face indices
    new_faces = [[old_to_new[v] for v in face] for face in new_faces]

    return new_verts, new_faces

def center_and_scale(verts, target_size=1.0):
    """Center model at origin and scale to target size"""
    if not verts:
        return verts

    # Find bounds
    min_v = [min(v[i] for v in verts) for i in range(3)]
    max_v = [max(v[i] for v in verts) for i in range(3)]

    # Center
    center = [(min_v[i] + max_v[i]) / 2 for i in range(3)]

    # Size
    size = max(max_v[i] - min_v[i] for i in range(3))
    if size < 1e-10:
        return verts

    scale = target_size / size

    # Transform
    return [vec_scale(vec_sub(v, center), scale) for v in verts]

def auto_orient(verts):
    """Rotate model so it stands upright (tallest axis = Y) and faces camera"""
    if not verts:
        return verts

    # Find which axis is tallest
    mins = [min(v[i] for v in verts) for i in range(3)]
    maxs = [max(v[i] for v in verts) for i in range(3)]
    sizes = [maxs[i] - mins[i] for i in range(3)]

    # Si el modelo es muy plano en Z (acostado), rotarlo para que mire bien
    if sizes[2] < sizes[0] * 0.5 and sizes[2] < sizes[1] * 0.5:
        verts = [rotate_x(v, math.pi / 2) for v in verts]

    return verts

def calc_camera_distance(verts, fov, screen_w, screen_h):
    """Calculate camera distance so model fills ~70% of screen"""
    if not verts:
        return 3.0
    
    # Get model extent
    max_extent = max(max(abs(v[i]) for v in verts) for i in range(3))
    if max_extent < 0.001:
        return 3.0
    
    # Projection formula: screen_y = -vy * (fov/z) * (h/2) + h/2
    # We want model edge to be at ~15% from screen edge
    # So: max_extent * (fov/dist) * (h/2) = 0.35 * h
    # Solving: dist = max_extent * fov / 0.70
    distance = max_extent * fov / 0.70
    
    return max(1.5, min(15.0, distance))

# ─── Built-in shapes ───

def make_cube():
    """1x1 cube centered at origin"""
    v = [
        [-0.5,-0.5,-0.5], [0.5,-0.5,-0.5], [0.5,0.5,-0.5], [-0.5,0.5,-0.5],
        [-0.5,-0.5,0.5],  [0.5,-0.5,0.5],  [0.5,0.5,0.5],  [-0.5,0.5,0.5],
    ]
    f = [
        [0,1,2,3], [4,5,6,7], [0,1,5,4],
        [2,3,7,6], [0,3,7,4], [1,2,6,5],
    ]
    return v, f

def make_icosphere(subdiv=1):
    """Generate icosphere vertices and faces"""
    t = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [
        vec_norm([-1, t, 0]), vec_norm([1, t, 0]), vec_norm([-1, -t, 0]), vec_norm([1, -t, 0]),
        vec_norm([0, -1, t]), vec_norm([0, 1, t]), vec_norm([0, -1, -t]), vec_norm([0, 1, -t]),
        vec_norm([t, 0, -1]), vec_norm([t, 0, 1]), vec_norm([-t, 0, -1]), vec_norm([-t, 0, 1]),
    ]
    faces = [
        [0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
        [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
        [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
        [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1],
    ]

    for _ in range(subdiv):
        midpoint_cache = {}
        new_faces = []

        def get_midpoint(i1, i2):
            key = (min(i1,i2), max(i1,i2))
            if key in midpoint_cache:
                return midpoint_cache[key]
            v1, v2 = verts[i1], verts[i2]
            mid = vec_norm([(v1[0]+v2[0])/2, (v1[1]+v2[1])/2, (v1[2]+v2[2])/2])
            idx = len(verts)
            verts.append(mid)
            midpoint_cache[key] = idx
            return idx

        for face in faces:
            a = get_midpoint(face[0], face[1])
            b = get_midpoint(face[1], face[2])
            c = get_midpoint(face[2], face[0])
            new_faces.extend([
                [face[0], a, c],
                [face[1], b, a],
                [face[2], c, b],
                [a, b, c],
            ])
        faces = new_faces

    return verts, faces

def make_torus(R=0.7, r=0.3, segments=24, rings=16):
    """Generate torus"""
    verts = []
    faces = []
    for i in range(rings):
        theta = 2 * math.pi * i / rings
        for j in range(segments):
            phi = 2 * math.pi * j / segments
            x = (R + r * math.cos(phi)) * math.cos(theta)
            y = r * math.sin(phi)
            z = (R + r * math.cos(phi)) * math.sin(theta)
            verts.append(vec3(x, y, z))
    for i in range(rings):
        for j in range(segments):
            a = i * segments + j
            b = i * segments + (j+1) % segments
            c = ((i+1) % rings) * segments + (j+1) % segments
            d = ((i+1) % rings) * segments + j
            faces.append([a, b, c, d])
    return verts, faces

# ─── Renderer ───

class ASCIIRenderer:
    SHADE_CHARS = " .:-=+*#%@"
    WIREFRAME_CHARS = " .,:;+=*#%@"

    def __init__(self, width=80, height=40, wireframe=False, shading=True, fov=3.0, distance=3.0):
        self.width = width
        self.height = height
        self.wireframe = wireframe
        self.shading = shading
        self.fov = fov
        self.distance = distance
        self.light_dir = vec_norm([0, 0, -1])

    def project(self, v):
        """Project 3D vertex to 2D screen coords"""
        z = v[2] + self.distance
        if z < 0.1:
            z = 0.1
        
        # Perspective projection
        f = self.fov / z
        
        # Screen coordinates
        # x: model space [-1,1] maps to screen width
        # y: model space [-1,1] maps to screen height
        # chars are ~2x taller than wide, so multiply x by 2
        sx = v[0] * f * (self.height / 2) * 2 + self.width / 2
        sy = -v[1] * f * (self.height / 2) + self.height / 2
        
        return int(sx), int(sy), z

    def render_frame(self, verts, faces, angle_x, angle_y, angle_z):
        """Render one frame to string"""
        # Transformar vértices
        transformed = []
        for v in verts:
            tv = rotate_x(v, angle_x)
            tv = rotate_y(tv, angle_y)
            tv = rotate_z(tv, angle_z)
            transformed.append(tv)

        # Buffers
        buf = [[' '] * self.width for _ in range(self.height)]
        zbuf = [[float('inf')] * self.width for _ in range(self.height)]

        if self.wireframe:
            self._render_lit_wireframe(transformed, faces, buf, zbuf)
        else:
            self._render_splat(transformed, faces, buf, zbuf)

        # Convertir buffer a string
        return '\n'.join(''.join(row) for row in buf)

    def _render_splat(self, verts, faces, buf, zbuf):
        """Render using point splatting - best for dense meshes at low resolution"""
        for face in faces:
            if len(face) < 3:
                continue

            # Get face vertices
            v0 = verts[face[0]]
            v1 = verts[face[1]]
            v2 = verts[face[2]]

            # Face normal
            e1 = vec_sub(v1, v0)
            e2 = vec_sub(v2, v0)
            normal = vec_cross(e1, e2)

            # Back-face culling
            if normal[2] < 0:
                continue

            normal = vec_norm(normal)

            # Lighting
            brightness = max(0, -vec_dot(normal, self.light_dir))
            shade_idx = min(len(self.SHADE_CHARS)-1,
                          int(brightness * (len(self.SHADE_CHARS)-1)))
            char = self.SHADE_CHARS[shade_idx]

            # Splat centroid
            cx = (v0[0] + v1[0] + v2[0]) / 3.0
            cy = (v0[1] + v1[1] + v2[1]) / 3.0
            cz = (v0[2] + v1[2] + v2[2]) / 3.0

            px, py, pz = self.project([cx, cy, cz])
            
            if 0 <= px < self.width and 0 <= py < self.height:
                if pz < zbuf[py][px]:
                    zbuf[py][px] = pz
                    buf[py][px] = char

            # Also splat vertices for more coverage
            for v in [v0, v1, v2]:
                px, py, pz = self.project(v)
                if 0 <= px < self.width and 0 <= py < self.height:
                    if pz < zbuf[py][px]:
                        zbuf[py][px] = pz
                        buf[py][px] = char

    def _render_lit_wireframe(self, verts, faces, buf, zbuf):
        """Render lit wireframe - each face's edges use the face's shading character"""
        drawn_edges = set()

        for face in faces:
            if len(face) < 3:
                continue

            # Get face vertices
            v0 = verts[face[0]]
            v1 = verts[face[1]]
            v2 = verts[face[2]]

            # Face normal
            e1 = vec_sub(v1, v0)
            e2 = vec_sub(v2, v0)
            normal = vec_cross(e1, e2)

            # Back-face culling
            if normal[2] < 0:
                continue

            normal = vec_norm(normal)

            # Lighting for this face
            brightness = max(0, -vec_dot(normal, self.light_dir))
            shade_idx = min(len(self.SHADE_CHARS)-1,
                          int(brightness * (len(self.SHADE_CHARS)-1)))
            char = self.SHADE_CHARS[shade_idx]

            # Project vertices
            p0 = self.project(v0)
            p1 = self.project(v1)
            p2 = self.project(v2)

            # Draw edges with this face's character
            for i in range(len(face)):
                a, b = face[i], face[(i+1) % len(face)]
                edge_key = (min(a,b), max(a,b))

                # Use brighter char if edge already drawn
                if edge_key in drawn_edges:
                    # Already drawn by adjacent face - use brighter char
                    bright_char = self.SHADE_CHARS[min(len(self.SHADE_CHARS)-1, shade_idx + 2)]
                    self._draw_line_with_z(p0 if i==0 else (p1 if i==1 else p2),
                                          p1 if i==0 else (p2 if i==1 else p0),
                                          bright_char, buf, zbuf)
                else:
                    drawn_edges.add(edge_key)
                    pts = [p0, p1, p2]
                    self._draw_line_with_z(pts[i], pts[(i+1)%3], char, buf, zbuf)

    def _render_wireframe(self, verts, faces, buf, zbuf):
        """Render wireframe"""
        drawn = set()
        for face in faces:
            for i in range(len(face)):
                a, b = face[i], face[(i+1) % len(face)]
                edge = (min(a,b), max(a,b))
                if edge in drawn:
                    continue
                drawn.add(edge)

                pa = self.project(verts[a])
                pb = self.project(verts[b])
                self._draw_line(pa, pb, '*', buf, zbuf)

    def _rasterize_triangle(self, p0, p1, p2, char, buf, zbuf):
        """Fill triangle using edge equation (barycentric coords)"""
        x0, y0, z0 = p0
        x1, y1, z1 = p1
        x2, y2, z2 = p2

        # Bounding box
        min_x = max(0, int(min(x0, x1, x2)))
        max_x = min(self.width - 1, int(max(x0, x1, x2)))
        min_y = max(0, int(min(y0, y1, y2)))
        max_y = min(self.height - 1, int(max(y0, y1, y2)))

        # Area (2x)
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        
        # For very small triangles, just plot the centroid
        if abs(area) < 0.5:
            cx = int((x0 + x1 + x2) / 3)
            cy = int((y0 + y1 + y2) / 3)
            cz = (z0 + z1 + z2) / 3
            if 0 <= cx < self.width and 0 <= cy < self.height:
                if cz < zbuf[cy][cx]:
                    zbuf[cy][cx] = cz
                    buf[cy][cx] = char
            return

        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                # Barycentric coords
                w0 = ((x1 - x) * (y2 - y) - (x2 - x) * (y1 - y)) / area
                w1 = ((x2 - x) * (y0 - y) - (x0 - x) * (y2 - y)) / area
                w2 = 1 - w0 - w1

                if w0 >= 0 and w1 >= 0 and w2 >= 0:
                    z = w0 * z0 + w1 * z1 + w2 * z2
                    if z < zbuf[y][x]:
                        zbuf[y][x] = z
                        buf[y][x] = char

    def _draw_line_with_z(self, p0, p1, char, buf, zbuf):
        """Bresenham line with Z-buffer interpolation"""
        x0, y0, z0 = p0
        x1, y1, z1 = p1

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        steps = max(dx, dy)
        if steps == 0:
            steps = 1

        step = 0
        while True:
            if 0 <= x0 < self.width and 0 <= y0 < self.height:
                # Interpolate Z
                t = step / steps if steps > 0 else 0
                z = z0 + t * (z1 - z0)

                if z < zbuf[y0][x0]:
                    zbuf[y0][x0] = z
                    buf[y0][x0] = char

            if x0 == x1 and y0 == y1:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

            step += 1

    def _draw_line(self, p0, p1, char, buf, zbuf):
        """Bresenham line"""
        x0, y0, z0 = p0
        x1, y1, z1 = p1

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        steps = max(dx, dy)
        if steps == 0:
            steps = 1

        while True:
            if 0 <= x0 < self.width and 0 <= y0 < self.height:
                t = abs(x0 - p0[0]) + abs(y0 - p0[1])
                t = t / (abs(x1 - p0[0]) + abs(y1 - p0[1]) + 0.001)
                z = z0 + t * (z1 - z0)
                if z < zbuf[y0][x0]:
                    zbuf[y0][x0] = z
                    buf[y0][x0] = char

            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

# ─── Main ───

def get_terminal_size():
    """Get terminal dimensions"""
    try:
        import shutil
        size = shutil.get_terminal_size((80, 40))
        return size.columns, size.lines - 2  # dejar espacio para prompt
    except:
        return 80, 40

def main():
    parser = argparse.ArgumentParser(
        description='Renderiza modelos 3D como ASCII art rotativo',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  ascii3d modelo.obj                    # Render OBJ file
  ascii3d modelo.stl                    # Render STL file
  ascii3d --shape cube                  # Built-in cube
  ascii3d --shape sphere                # Built-in sphere
  ascii3d --shape torus                 # Built-in torus
  ascii3d modelo.obj --speed 0.02       # Más lento
  ascii3d modelo.obj --wireframe        # Solo wireframe
  ascii3d modelo.obj --width 120        # Más ancho
  ascii3d modelo.obj --axis x           # Rotar solo en X
        """)
    parser.add_argument('file', nargs='?', help='Archivo 3D (OBJ/STL)')
    parser.add_argument('--shape', choices=['cube', 'sphere', 'torus', 'ico'],
                       help='Usar forma built-in')
    parser.add_argument('--speed', type=float, default=0.04,
                       help='Velocidad de rotación (default: 0.04)')
    parser.add_argument('--wireframe', '-w', action='store_true',
                       help='Modo wireframe (default para STL)')
    parser.add_argument('--solid', action='store_true',
                       help='Forzar modo sólido (default para formas built-in)')
    parser.add_argument('--width', type=int, default=0,
                       help='Ancho en chars (default: auto)')
    parser.add_argument('--height', type=int, default=0,
                       help='Alto en chars (default: auto)')
    parser.add_argument('--axis', choices=['x', 'y', 'z', 'all'], default='all',
                       help='Eje de rotación')
    parser.add_argument('--fov', type=float, default=3.0,
                       help='Campo de visión (default: 3.0)')
    parser.add_argument('--distance', type=float, default=0,
                       help='Distancia cámara (0=auto, default: 0)')
    parser.add_argument('--no-shade', action='store_true',
                       help='Sin shading')
    parser.add_argument('--max-faces', type=int, default=5000,
                       help='Máximo de caras antes de decimar (default: 5000)')
    parser.add_argument('--scale', type=float, default=4.0,
                       help='Escala del modelo (default: 4.0)')

    args = parser.parse_args()

    # Cargar modelo
    if args.shape:
        shapes = {
            'cube': make_cube,
            'sphere': lambda: make_icosphere(2),
            'ico': lambda: make_icosphere(1),
            'torus': make_torus,
        }
        verts, faces = shapes[args.shape]()
        model_name = args.shape
    elif args.file:
        if not os.path.exists(args.file):
            print(f"Error: {args.file} no encontrado", file=sys.stderr)
            sys.exit(1)
        verts, faces = load_model(args.file)
        model_name = os.path.basename(args.file)
        print(f"Cargado: {len(verts)} vértices, {len(faces)} caras")
    else:
        parser.print_help()
        sys.exit(1)

    # Tamaño terminal - leave 2 lines for status bar
    if args.width and args.height:
        w, h = args.width, args.height
    else:
        term_w, term_h = get_terminal_size()
        w = args.width if args.width else term_w
        h = args.height if args.height else term_h - 2  # leave room for status

    # Decimate if too many faces
    original_faces = len(faces)
    if len(faces) > args.max_faces:
        print(f"Decimating: {len(faces)} faces -> ", end="", flush=True)
        verts, faces = decimate_model(verts, faces, max_faces=args.max_faces)
        print(f"{len(faces)} faces")

    # Auto-orient (stand up models that are lying down)
    if args.file:
        verts = auto_orient(verts)

    # Center and scale model
    verts = center_and_scale(verts, target_size=1.0)
    
    # Auto-calculate camera distance
    auto_distance = calc_camera_distance(verts, args.fov, w, h)

    # Update info
    if args.file:
        model_name = f"{os.path.basename(args.file)} ({len(verts)}v {len(faces)}f"
        if original_faces != len(faces):
            model_name += f"/{original_faces} orig"
        model_name += ")"

    # Default to wireframe for STL (looks better)
    use_wireframe = True if (args.file and args.file.lower().endswith('.stl')) else args.wireframe
    
    # Setup renderer
    cam_distance = args.distance if args.distance > 0 else auto_distance
    renderer = ASCIIRenderer(
        width=w,
        height=h,
        wireframe=use_wireframe,
        shading=not args.no_shade,
        fov=args.fov,
        distance=cam_distance
    )

    # Ocultar cursor y clear
    sys.stdout.write('\033[?25l')  # hide cursor
    sys.stdout.write('\033[2J')    # clear screen
    sys.stdout.write('\033[H')     # cursor home
    sys.stdout.flush()

    # Manejar Ctrl+C
    def cleanup(sig=None, frame=None):
        sys.stdout.write('\033[?25h')  # show cursor
        sys.stdout.write('\033[2J')    # clear
        sys.stdout.write('\033[H')     # home
        sys.stdout.flush()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)

    # Info overlay
    info = f" ascii3d | {model_name} | {len(verts)}v {len(faces)}f | Ctrl+C exit "

    # Camera state: orbital camera around fixed object
    cam_yaw = 0.0      # horizontal rotation (Y axis orbit)
    cam_pitch = 0.0    # vertical rotation (X axis orbit)
    
    # State machine: ROTATING -> USER_CONTROL -> SNAP_BACK -> ROTATING
    STATE_ROTATING = 0
    STATE_USER_CONTROL = 1
    STATE_SNAP_BACK = 2
    
    state = STATE_ROTATING
    auto_rotate_speed = args.speed
    last_input_time = time.time()
    snap_back_delay = 3.0
    
    # Setup keyboard input
    kb = KeyboardInput()
    kb.start()
    
    try:
        while True:
            current_time = time.time()
            keys = kb.get_keys()
            
            # Quit
            if 'quit' in keys or 'escape' in keys:
                break
            
            # Check if any movement key pressed this frame
            has_input = bool(keys & {'w', 'a', 's', 'd', 'up', 'down', 'left', 'right'})
            
            if has_input:
                state = STATE_USER_CONTROL
                last_input_time = current_time
                
                # Move camera based on keys
                move_speed = 0.04
                if 'w' in keys or 'up' in keys:
                    cam_pitch -= move_speed
                if 's' in keys or 'down' in keys:
                    cam_pitch += move_speed
                if 'a' in keys or 'left' in keys:
                    cam_yaw -= move_speed
                if 'd' in keys or 'right' in keys:
                    cam_yaw += move_speed
                
                # Clamp pitch
                cam_pitch = max(-1.4, min(1.4, cam_pitch))
            
            else:
                # No input this frame
                time_since_input = current_time - last_input_time
                
                if state == STATE_USER_CONTROL:
                    if time_since_input > snap_back_delay:
                        state = STATE_SNAP_BACK
                
                elif state == STATE_SNAP_BACK:
                    # Smooth correction: pitch -> 0
                    if abs(cam_pitch) > 0.01:
                        cam_pitch *= 0.92  # exponential decay
                    else:
                        cam_pitch = 0.0
                        state = STATE_ROTATING
                
                elif state == STATE_ROTATING:
                    # Auto-rotate horizontally
                    cam_yaw += auto_rotate_speed
            
            # Use renderer's render_frame with inverted angles (camera orbits, not object)
            frame = renderer.render_frame(verts, faces, -cam_pitch, -cam_yaw, 0)
            
            # Output - clear and redraw
            sys.stdout.write('\033[H')  # cursor home
            sys.stdout.write('\033[J')  # clear from cursor to end
            
            # Write frame line by line
            frame_lines = frame.split('\n')
            for i in range(h):
                if i < len(frame_lines):
                    sys.stdout.write(frame_lines[i][:w])
                sys.stdout.write('\033[E')  # move to next line
            
            # Status bar at bottom
            yaw_deg = int(math.degrees(cam_yaw) % 360)
            pitch_deg = int(math.degrees(cam_pitch))
            state_names = {STATE_ROTATING: "ROTATING", STATE_USER_CONTROL: "CONTROL", STATE_SNAP_BACK: "SNAP-BACK"}
            status = f" Yaw:{yaw_deg}° Pitch:{pitch_deg}° [{state_names[state]}]"
            controls = " WASD/move | Q/quit"
            line = info + status + controls
            sys.stdout.write(line[:w])
            sys.stdout.write('\033[K')  # clear rest of line
            
            sys.stdout.flush()
            time.sleep(1/30)

    except Exception as e:
        cleanup()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        kb.stop()

if __name__ == '__main__':
    main()
