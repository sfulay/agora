'use strict';

(async function () {
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  const animationCanvas = document.getElementById('animation-canvas');
  const animationCtx = animationCanvas.getContext('2d');
  const imageElements = {};
  const optionElements = {};
  const userIcon = new Image();

  let colorPicker;
  let iconWidth, iconHeight;
  
  window.onload = async function() {
    colorPicker = new jscolor(document.getElementById('colorPicker'), {
      borderRadius: 10,
      alpha: 0.5,
      forceStyle: false,
      mode: 'HSV',
      onInput: 'updateColorFromPicker(this)'
    });
    await Promise.all([preloadOptionImages(), preloadCanvasImages(dirFrames)]);
    updateIcon();
    const frames = applyAnimationFrames();
    startAnimationLoop(frames);
  }

  const p = '../../assets/pipoya-sprites/5/'
  userIcon.src = p + 'empty.png';

  let currentPart = 0;
  const partNames = ['base', 'clothes', 'eyes', 'hair', 'hat', 'glasses', 'beard'];
  const parts = {
    base: Array.from({ length: 4 }, (_, i) => `${p}00Skin/${i + 1}.png`),
    clothes: Array.from({ length: 46 }, (_, i) => `${p}01Costume/${i + 1}.png`),
    eyes: Array.from({ length: 23 }, (_, i) => `${p}02Eye/${i + 1}.png`),
    hair: Array.from({ length: 34 }, (_, i) => `${p}03Hair/${i + 1}.png`),
    hat: Array.from({ length: 15 }, (_, i) => `${p}05Hat/${i + 1}.png`),
    glasses: Array.from({ length: 11 }, (_, i) => `${p}06Glasses/${i + 1}.png`),
    beard: Array.from({ length: 5 }, (_, i) => `${p}09Beard/${i + 1}.png`),
  };

  const partColorSettings = {
    base: { red: 128, green: 128, blue: 128, alpha: 0},
    clothes: { red: 128, green: 128, blue: 128, alpha: 0},
    eyes: { red: 128, green: 128, blue: 128, alpha: 0},
    hair: { red: 128, green: 128, blue: 128, alpha: 0 },
    hat: { red: 128, green: 128, blue: 128, alpha: 0 },
    glasses: { red: 128, green: 128, blue: 128, alpha: 0 },
    beard: { red: 128, green: 128, blue: 128, alpha: 0 },
  };

  const selectedOptions = {
    base: parts['base'][Math.floor(Math.random() * parts['base'].length)],
    clothes: parts['clothes'][Math.floor(Math.random() * parts['clothes'].length)],
    eyes: parts['eyes'][Math.floor(Math.random() * parts['eyes'].length)],
    hair: parts['hair'][Math.floor(Math.random() * parts['hair'].length)],
    hat: parts['hat'][14],
    glasses: parts['glasses'][10],
    beard: parts['beard'][3],
  };

  function preloadOptionImages() {
    const promises = [];
    Object.keys(parts).forEach(part => {
      optionElements[part] = parts[part].map(path => {
        const img = new Image();
        const promise = new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = reject;
        });
        promises.push(promise);
        img.className = 'option';
        img.onclick = () => selectOption(part, path);
        img.src = path;
        return img;
      });
    });
    return Promise.all(promises);
  }

  function preloadCanvasImages(dirFrames) {
    const promises = [];

    Object.keys(parts).forEach(part => {
      imageElements[part] = {};
      parts[part].forEach(path => {
        // frame 5 static view
        const staticFramePath = path.replace('/5/', '/5/');
        if (!imageElements[part][staticFramePath]) {
          promises.push(preloadImage(staticFramePath, part));
        }

        dirFrames.forEach(frame => {
          const animationPath = path.replace('/5/', `/${frame}/`);
          if (!imageElements[part][animationPath]) {
            promises.push(preloadImage(animationPath, part));
          }
        });
      });
    });

    return Promise.all(promises);
  }

  function preloadImage(path, part) {
    const img = new Image();
    const promise = new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = reject;
    });
    img.src = path;
    imageElements[part][path] = img;
    return promise;
  }



  function loadPartOptions() {
    const optionsContainer = document.getElementById('options-container');
    optionsContainer.innerHTML = '';
    optionElements[partNames[currentPart]].forEach(imgElement => {
      imgElement.draggable = false;
      optionsContainer.appendChild(imgElement);
      });
      updateSelectedOption();
  }

  function selectOption(part, path) {
 		selectedOptions[part] = path;
 		if (['hat', 'glasses', 'beard'].includes(part)) {
 			updateHeadSelection(part);
 		} else {
 			updateSelectedOption();
 		}
 		preloadSelectedParts().then(() => {
 			updateIcon();
 		});
 	}

  function updateSelectedOption() {
    const imgs = document.querySelectorAll('#options-container .option');
    imgs.forEach((img, index) => {
      img.classList.remove('active');
      const partOption = parts[partNames[currentPart]][index];
      const selectedOption = selectedOptions[partNames[currentPart]];
      if (partOption === selectedOption) {
        img.classList.add('active');
      }
    });
  }


  function updateHeadSelection(headPart) {
      const imgs = document.querySelectorAll(`#options-container .${headPart}`);
      imgs.forEach((img, index) => {
          img.classList.remove('active');
          const partOption = parts[headPart][index];
          const selectedOption = selectedOptions[headPart];
          if (partOption === selectedOption) {
              img.classList.add('active');
          }
      });
  }



  window.changeTab = function (tabId) {
    const tab = document.getElementById(tabId);
    if (!tab) {
      console.error('Invalid tab element');
      return;
    }
    const tabs = document.querySelectorAll('.tab-button');
    tabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');

    if (tabId === 'head') {
      currentPart = partNames.indexOf('beard');
      const currentColor = partColorSettings[partNames[currentPart]];
      colorPicker.fromRGBA(currentColor.red, currentColor.green, currentColor.blue);
      loadHeadOptions();
    } else {
      currentPart = partNames.indexOf(tabId);
      const currentColor = partColorSettings[partNames[currentPart]];
      colorPicker.fromRGBA(currentColor.red, currentColor.green, currentColor.blue);
      loadPartOptions();
    }
  };

  function loadHeadOptions() {
    const optionsContainer = document.getElementById('options-container');
    optionsContainer.innerHTML = '';

    ['hat', 'glasses', 'beard'].forEach(part => {
      const partContainer = document.createElement('div');
      partContainer.className = 'part-container';

      const partLabel = document.createElement('div');
      partLabel.textContent = part.charAt(0).toUpperCase() + part.slice(1);
      partContainer.appendChild(partLabel);

      optionElements[part].forEach(imgElement => {
        imgElement.draggable = false;
        imgElement.classList.add(part);
        partContainer.appendChild(imgElement);
      });

      optionsContainer.appendChild(partContainer);
    });

    ['hat', 'glasses', 'beard'].forEach(headPart => {
      updateHeadSelection(headPart);
});

  }




  window.updateColorFromPicker = function(picker) {
      const rgbaString = picker.toRGBAString();
      const colorValues = rgbaString.split('(')[1].slice(0, -1);
      const alpha = rgbaString.split(',')[3].slice(0, -1);
      const [red, green, blue] = colorValues.split(',').map(Number);

      if (['hat', 'glasses', 'beard'].includes(partNames[currentPart])) {
          ['hat', 'glasses', 'beard'].forEach(headPart => {
              partColorSettings[headPart] = { red, green, blue, alpha };
          });
      } else {
          partColorSettings[partNames[currentPart]] = { red, green, blue, alpha };
      }

      updateIcon();
  };

    
  function applyColorFilterToImage(image, color, part) {
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = canvas.width;
    tempCanvas.height = canvas.height;
    const tempCtx = tempCanvas.getContext('2d');

    tempCtx.imageSmoothingEnabled = false;

    tempCtx.drawImage(image, 0, 0, canvas.width, canvas.height);

    // color blend
    tempCtx.globalCompositeOperation = 'source-atop';
    let opacity = 0;

    if (part === 'base') {
      opacity = 0.1;
    } else if(part === 'clothes') {
      opacity = 0.4;
    } else if(part === 'eyes') {
      opacity = 0.2;
    } else if(part === 'hair') {
      opacity = 0.7;
    } else if(part === 'hat') {
      opacity = 0.3;
    } else if (part === 'glasses') {
      opacity = 0.5;
    } else if (part === 'beard') {
      opacity = 0.7;
    }
    

    opacity = color.alpha * opacity;

    tempCtx.fillStyle = `rgba(${color.red}, ${color.green}, ${color.blue}, ${opacity})`; // opacity
    // TODO per-part opacity
    tempCtx.fillRect(0, 0, canvas.width, canvas.height);
    tempCtx.globalCompositeOperation = 'source-over';

    return tempCanvas;
}

  function updateIcon() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    partNames.forEach(part => {
        const path = selectedOptions[part];
        if (path && imageElements[part][path]) {
            const colorSettings = partColorSettings[part];
            const adjustedImageCanvas = applyColorFilterToImage(imageElements[part][path], colorSettings, part);
            ctx.drawImage(adjustedImageCanvas, 0, 0, canvas.width, canvas.height);
        }
    });
    
    ctx.drawImage(userIcon, 0, 0, canvas.width, canvas.height);
    const frames = applyAnimationFrames();
    startAnimationLoop(frames);
  }

  let dirFrames = ['3', '7', '11', '7'];
  
  const dirFrameSets = [
    ['3', '7', '11', '7'], // Right
    ['4', '8', '12', '8'], // Back
    ['2', '6', '10', '6'], // Left
    ['1', '5', '9', '5'],  // Front
  ];

  let animDir = 0;

  function updateDirection() {
    animDir = (animDir + 1) % dirFrameSets.length;
    dirFrames = dirFrameSets[animDir];

    preloadSelectedParts().then(() => {
      updateAnimation();
    });
  }


  document.getElementById('animationDirection').addEventListener('click', updateDirection);


  function applyAnimationFrames() {
    const frameCanvases = [];

    dirFrames.forEach(frame => {
      const frameCanvas = document.createElement('canvas');
      frameCanvas.width = canvas.width;
      frameCanvas.height = canvas.height;
      const frameCtx = frameCanvas.getContext('2d');
      frameCtx.imageSmoothingEnabled = false;

      partNames.forEach(part => {
        const path = selectedOptions[part];
        if (path && imageElements[part][path]) {
          const colorSettings = partColorSettings[part];
          const animationPath = path.replace('/5/', `/${frame}/`);
          if (imageElements[part][animationPath]) {
            const adjustedImageCanvas = applyColorFilterToImage(imageElements[part][animationPath], colorSettings, part);
            frameCtx.drawImage(adjustedImageCanvas, 0, 0, canvas.width, canvas.height);
          }
        }
      });

      frameCanvases.push(frameCanvas);
    });

    return frameCanvases;
  }

  let currentAnimationFrame = 0;
  let frameDelayCounter = 0;
  const frameDelay = 30;
  let animationFrameId = null;

  function startAnimationLoop(frames) {
    if (animationFrameId !== null) {
      cancelAnimationFrame(animationFrameId);
    }

    function animate() {
      if (frameDelayCounter % frameDelay === 0) {
        animationCtx.clearRect(0, 0, animationCanvas.width, animationCanvas.height);
        animationCtx.drawImage(frames[currentAnimationFrame], 0, 0);
        currentAnimationFrame = (currentAnimationFrame + 1) % frames.length;
        frameDelayCounter = 0;
      }

      frameDelayCounter++;
      animationFrameId = requestAnimationFrame(animate);
    }

    animate();
  }

  function updateAnimation() {
    const frames = applyAnimationFrames();
    startAnimationLoop(frames);
  }



  window.updateColor = function(picker) {
      const rgbColor = picker.rgb;
      partColorSettings[partNames[currentPart]].red = rgbColor[0];
      partColorSettings[partNames[currentPart]].green = rgbColor[1];
      partColorSettings[partNames[currentPart]].blue = rgbColor[2];
      updateIcon();
  };

    userIcon.onload = () => {
      ctx.imageSmoothingEnabled = false;
      preloadOptionImages();
      preloadCanvasImages(['5']);
      preloadSelectedParts();
      loadPartOptions();
      updateIcon();
    };
  
  function preloadSelectedParts() {
    const promises = [];
    const framesToPreload = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'];

    Object.keys(selectedOptions).forEach(part => {
      const selectedPath = selectedOptions[part];
      framesToPreload.forEach(frame => {
        const framePath = selectedPath.replace('/5/', `/${frame}/`);
        if (!imageElements[part][framePath]) {
          promises.push(preloadImage(framePath, part));
        }
      });
    });

    return Promise.all(promises);
  }

  
  function renderFrame(frameNumber) {
    const frameCanvas = document.createElement('canvas');
    frameCanvas.width = canvas.width;
    frameCanvas.height = canvas.height;
    const frameCtx = frameCanvas.getContext('2d');

    partNames.forEach(part => {
      const path = selectedOptions[part];
      if (path && imageElements[part][path]) {
        const colorSettings = partColorSettings[part];
        const framePath = path.replace('/5/', `/${frameNumber}/`);
        const adjustedImageCanvas = applyColorFilterToImage(imageElements[part][framePath], colorSettings, part);
        frameCtx.drawImage(adjustedImageCanvas, 0, 0, canvas.width, canvas.height);
      }
    });

    frameCtx.drawImage(userIcon, 0, 0, canvas.width, canvas.height);

    return frameCanvas;
  }

  
  async function drawSpritesheet() {
    const frameWidth = canvas.width;
    const frameHeight = canvas.height;
    const spritesheetCanvas = document.createElement('canvas');
    const spritesheetCtx = spritesheetCanvas.getContext('2d');

    const columns = 3;
    const rows = 4;
    spritesheetCanvas.width = frameWidth * columns;
    spritesheetCanvas.height = frameHeight * rows;

    let x = 0, y = 0;

    for (let i = 1; i <= 12; i++) {
      const frameCanvas = await renderFrame(i.toString());

      spritesheetCtx.drawImage(frameCanvas, x, y, frameWidth, frameHeight);

      y += frameHeight;
      if (i % rows === 0) {
        x += frameWidth;
        y = 0;
      }
    }

    return spritesheetCanvas;
  }


  async function saveSpritesheet() {
    await preloadSelectedParts();
    const spritesheetCanvas = await drawSpritesheet();
    const link = document.createElement('a');
    spritesheetCanvas.toBlob(blob => {
      const url = URL.createObjectURL(blob);
      link.href = url;
      link.download = 'spritesheet.png';
      link.click();
      URL.revokeObjectURL(url);
    });
  }


  // function saveImage() {
  //     const image = canvas.toDataURL('image/png');
  //     const link = document.createElement('a');
  //     link.download = 'my-icon.png';
  //     link.href = image;
  //     link.click();
  // }

  async function saveAll() {
      await preloadSelectedParts();

      const frontFrame = renderFrame('5');
      await saveCanvas(frontFrame, 'front.png');

      const spritesheet = await drawSpritesheet();
      await saveCanvas(spritesheet, 'spritesheet.png');

      const directions = ['right', 'back', 'left', 'front'];
      for (let i = 0; i < dirFrameSets.length; i++) {
          dirFrames = dirFrameSets[i];
          const frames = applyAnimationFrames();
          await saveGif(frames, directions[i]);
      }
  }

  async function saveCanvas(canvas, filename) {
      return new Promise(resolve => {
          canvas.toBlob(blob => {
              const url = URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = filename;
              link.click();
              URL.revokeObjectURL(url);
              resolve();
          });
      });
  }

  async function saveGif(frames, directionName) {
      const gif = new GIF({
        workers: 2,
        quality: 0,
        transparent: 'rgba(0,0,0,0)',
        globalPalette: true,
      });

      frames.forEach(frameCanvas => {
          gif.addFrame(frameCanvas, { delay: 200 });
      });

      return new Promise(resolve => {
          gif.on('finished', function(blob) {
              const url = URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = `${directionName}.gif`;
              link.click();
              URL.revokeObjectURL(url);
              resolve();
          });

          gif.render();
      });
  }

  const saveButton = document.getElementById('saveButton');
  saveButton.addEventListener('click', saveAll);


})();

