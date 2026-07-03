axios.defaults.withCredentials = true;
let scene, camera, renderer, chromosomeMesh, composer;

function openChromosomeWindow() {
    if (!selectedPatient) {
        showToast("الرجاء اختيار مريض أولاً", "error");
        return;
    }

    let coords = null;
    if (selectedPatient.genomic_inputs && selectedPatient.genomic_inputs.length > 0) {
        const latestTest = selectedPatient.genomic_inputs[selectedPatient.genomic_inputs.length - 1];
        if (latestTest.output && latestTest.output.coordinates) {
            coords = latestTest.output.coordinates;
        }
    }

    document.getElementById('viewer-container').style.display = 'block';
    const modal = document.getElementById('chromosome-modal');
    if (modal) modal.style.display = 'block';

    const titleEl = document.getElementById('modalTitle');
    if(titleEl) titleEl.innerText = `محاكي التركيب الفراغي للمريض: ${selectedPatient.name || 'غير مسمى'} (MRN: ${selectedPatient.mrn})`;

    setTimeout(() => {
        buildChromosome3DRenderer(coords);
    }, 50);
}

function closeChromosomeWindow() {
    const modal = document.getElementById('chromosome-modal');
    if (modal) modal.style.display = 'none';
    document.getElementById('viewer-container').style.display = 'none';
    
    if (renderer) {
        renderer.dispose();
        const container = document.getElementById('canvas-3d-space');
        if (container) {
            while (container.firstChild) container.removeChild(container.firstChild);
        }
    }
}

function buildChromosome3DRenderer(coordinates) {
    let finalCoordinates = coordinates;
    if (!finalCoordinates || finalCoordinates.length === 0) {
        finalCoordinates = generateHelixPoints(Math.random() * 100);
    }
    
    const container = document.getElementById('canvas-3d-space');
    if (!container) return;
    
    // تنظيف الحاوية لتجنب تكرار الرسم في حال فتح العارض أكثر من مرة
    while (container.firstChild) container.removeChild(container.firstChild);

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.z = 40;

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.3);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0x38bdf8, 1.0);
    directionalLight.position.set(1, 1, 1).normalize();
    scene.add(directionalLight);

    // ══ إعداد تأثير الهولوغرام المضيء (Bloom) ══
    const renderScene = new THREE.RenderPass(scene, camera);
    const bloomPass = new THREE.UnrealBloomPass(
        new THREE.Vector2(container.clientWidth, container.clientHeight), 
        1.5, 0.4, 0.85
    );
    bloomPass.threshold = 0.1;
    bloomPass.strength = 1.8; 
    bloomPass.radius = 0.5;

    composer = new THREE.EffectComposer(renderer);
    composer.addPass(renderScene);
    composer.addPass(bloomPass);

    const points = finalCoordinates.map(pt => new THREE.Vector3(pt.x, pt.y, pt.z));
    const curve = new THREE.CatmullRomCurve3(points);
    const geometry = new THREE.TubeGeometry(curve, 100, 0.7, 10, false);
    
    // الخامة المضيئة (Wireframe)
    const material = new THREE.MeshStandardMaterial({ 
        color: 0x38bdf8, 
        emissive: 0x38bdf8,       
        emissiveIntensity: 0.6,   
        wireframe: true,          
        transparent: true,
        opacity: 0.9
    });

    // تحديث الأبعاد عند تصغير وتكبير الشاشة
    window.addEventListener('resize', () => {
        if (renderer && camera && composer && container) {
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
            composer.setSize(container.clientWidth, container.clientHeight);
        }
    });

    chromosomeMesh = new THREE.Mesh(geometry, material);
    scene.add(chromosomeMesh);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    let isAutoRotating = true;
    controls.addEventListener('start', () => { isAutoRotating = false; });

    function animate() {
        const modal = document.getElementById('chromosome-modal');
        if(!modal || modal.style.display === 'none') return;
        
        requestAnimationFrame(animate);

        if (isAutoRotating) {
            chromosomeMesh.rotation.x += 0.002;
            chromosomeMesh.rotation.y += 0.004;
        }

        controls.update(); 
        composer.render(); // العرض باستخدام الكومبوزر للإضاءة بدل الريندر العادي
    }
    animate();
}

function generateHelixPoints(seed) {
    const points = [];
    let x = 0, y = 0, z = 0;
    for (let i = 0; i < 70; i++) {
        x = Math.sin(i * 0.4 + seed) * 12;
        y = (i - 35) * 0.6;
        z = Math.cos(i * 0.4 + seed) * 12;
        points.push({ x: x, y: y, z: z });
    }
    return points;
}