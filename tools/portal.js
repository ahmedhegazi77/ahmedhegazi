/* WebGL space */

const scene = new THREE.Scene()

const camera = new THREE.PerspectiveCamera(
75,
window.innerWidth/window.innerHeight,
0.1,
1000
)

const renderer = new THREE.WebGLRenderer({
canvas:document.getElementById("space")
})

renderer.setSize(window.innerWidth,window.innerHeight)

camera.position.z = 5

/* النجوم */

const starGeometry = new THREE.BufferGeometry()

const starCount = 2000

const positions = []

for(let i=0;i<starCount;i++){

positions.push(
(Math.random()-0.5)*1000,
(Math.random()-0.5)*1000,
(Math.random()-0.5)*1000
)

}

starGeometry.setAttribute(
'position',
new THREE.Float32BufferAttribute(positions,3)
)

const starMaterial = new THREE.PointsMaterial({
color:0xffffff
})

const stars = new THREE.Points(starGeometry,starMaterial)

scene.add(stars)

/* الشهب */

function createMeteor(){

const geometry = new THREE.SphereGeometry(0.05)

const material = new THREE.MeshBasicMaterial({color:0xffffff})

const meteor = new THREE.Mesh(geometry,material)

meteor.position.set(
(Math.random()-0.5)*20,
10,
(Math.random()-0.5)*20
)

scene.add(meteor)

function animateMeteor(){

meteor.position.y -=0.2
meteor.position.x +=0.1

if(meteor.position.y<-10){

scene.remove(meteor)

}else{

requestAnimationFrame(animateMeteor)

}

}

animateMeteor()

}

setInterval(createMeteor,2000)

/* الحركة */

function animate(){

requestAnimationFrame(animate)

stars.rotation.y +=0.0005

renderer.render(scene,camera)

}

animate()

/* العيون */

document.addEventListener("mousemove",e=>{

document.querySelectorAll(".pupil").forEach(p=>{

let x=(e.clientX/window.innerWidth)*20
let y=(e.clientY/window.innerHeight)*20

p.style.transform=`translate(${x}px,${y}px)`

})

})

/* انفجار ضوئي */

document.querySelectorAll(".card").forEach(card=>{

card.addEventListener("click",e=>{

let flash=document.createElement("div")

flash.className="flash"

flash.style.left=e.clientX+"px"
flash.style.top=e.clientY+"px"

document.body.appendChild(flash)

setTimeout(()=>flash.remove(),600)

})

})

/* الموسيقى */

let music=document.getElementById("bgmusic")
let btn=document.getElementById("musicBtn")

btn.innerHTML="▶"

btn.onclick=()=>{

if(music.paused){

music.play()
btn.innerHTML="❚❚"
btn.classList.add("playing")

}else{

music.pause()
btn.innerHTML="▶"
btn.classList.remove("playing")

}

}