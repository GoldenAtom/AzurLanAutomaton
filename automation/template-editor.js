(() => {
 const el=id=>document.getElementById(id), canvas=el('crop-canvas'), ctx=canvas.getContext('2d');
 const preview=el('crop-preview'), pctx=preview.getContext('2d');
 const fields=['crop-x1','crop-y1','crop-x2','crop-y2'].map(el);
 let frame=null,source=null,selection=null,start=null,busy=false;
 async function request(action,payload){
  const response=await fetch('/api/templates/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Automaton-Control':'1'},body:JSON.stringify(payload)});
  const result=await response.json();if(!response.ok)throw Error(result.error);return result;
 }
 function status(text){el('editor-status').textContent=text;}
 function valid(){return selection&&selection.every(Number.isInteger)&&selection[0]>=0&&selection[1]>=0&&selection[2]<=canvas.width&&selection[3]<=canvas.height&&selection[2]-selection[0]>=4&&selection[3]-selection[1]>=4;}
 function draw(){
  if(!source)return;ctx.drawImage(source,0,0);
  el('template-save').disabled=busy||!valid();
  if(!valid()){preview.width=0;preview.height=0;el('crop-size').textContent='Drag a crop or enter coordinates (minimum 4×4 pixels).';return;}
  const [x1,y1,x2,y2]=selection,w=x2-x1,h=y2-y1;
  ctx.fillStyle='rgba(0,0,0,.45)';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(source,x1,y1,w,h,x1,y1,w,h);
  ctx.strokeStyle='#80ffe0';ctx.lineWidth=Math.max(2,canvas.width/480);ctx.strokeRect(x1,y1,w,h);
  preview.width=w;preview.height=h;pctx.drawImage(source,x1,y1,w,h,0,0,w,h);
  el('crop-size').textContent=`Crop: ${w} × ${h} native pixels · (${x1}, ${y1}) to (${x2}, ${y2})`;
 }
 function setSelection(values){selection=values;fields.forEach((field,i)=>field.value=values[i]);draw();}
 function point(event){const rect=canvas.getBoundingClientRect();return [Math.max(0,Math.min(canvas.width,Math.round((event.clientX-rect.left)*canvas.width/rect.width))),Math.max(0,Math.min(canvas.height,Math.round((event.clientY-rect.top)*canvas.height/rect.height)))];}
 function updateDrag(event){if(!start)return;const end=point(event);setSelection([Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])]);}
 canvas.addEventListener('pointerdown',event=>{if(busy||!source)return;start=point(event);canvas.setPointerCapture(event.pointerId);updateDrag(event);});
 canvas.addEventListener('pointermove',updateDrag);
 canvas.addEventListener('pointerup',event=>{updateDrag(event);start=null;});
 canvas.addEventListener('pointercancel',()=>start=null);
 fields.forEach(field=>field.addEventListener('input',()=>{selection=fields.map(f=>Number(f.value));draw();}));
 el('crop-full').onclick=()=>setSelection([0,0,canvas.width,canvas.height]);
 function target(){return el('template-new-target').value.trim()||el('template-target').value;}
 function templateName(){return el('template-new-name').value.trim()||el('template-name').value;}
 function destination(){el('template-destination').textContent=`Save as: local-templates/targets/${target()}/${el('template-kind').value}/${templateName()}/${el('template-variant').value}.png`;}
 function names(){el('template-name').replaceChildren();const kind=el('template-kind').value,selected=target();for(const asset of frame.assets[kind].filter(item=>item.target===selected)){const option=document.createElement('option');option.value=asset.name;option.textContent=asset.name;el('template-name').append(option);}destination();}
 function targets(){const select=el('template-target'),previous=select.value;select.replaceChildren();const values=Object.keys(frame.targets);if(!values.length)values.push('general');for(const name of values){const option=document.createElement('option');option.value=name;option.textContent=name;select.append(option);}if(values.includes(previous))select.value=previous;names();}
 el('template-kind').onchange=names;el('template-target').onchange=names;el('template-new-target').oninput=names;el('template-new-name').oninput=destination;el('template-name').onchange=destination;el('template-variant').oninput=destination;
 el('editor-capture').onclick=async()=>{
  if(busy)return;busy=true;el('editor-capture').disabled=true;el('template-save').disabled=true;status('Capturing original Android pixels…');
  try{const result=await request('capture',{});const image=new Image();image.src=result.image;await image.decode();frame=result;source=image;selection=null;canvas.width=result.width;canvas.height=result.height;canvas.hidden=false;el('crop-fields').hidden=false;el('editor-size').textContent=` ${result.width} × ${result.height}`;el('template-download').hidden=true;targets();draw();status('Drag a rectangle on the screenshot. This capture is available for 15 minutes.');}
  catch(error){status(error.message);}finally{busy=false;el('editor-capture').disabled=false;draw();}
 };
 el('template-save').onclick=async()=>{
  if(busy||!valid())return;busy=true;el('template-save').disabled=true;el('editor-capture').disabled=true;status('Saving lossless crop…');
  try{const folder=target(),name=templateName(),kind=el('template-kind').value;const result=await request('save',{token:frame.token,region:selection,kind,target:folder,name,variant:el('template-variant').value});status(`${result.message} Saved ${result.path} (${result.width} × ${result.height}).`);el('template-download').href=result.image;el('template-download').download=result.filename;el('template-download').hidden=false;
   if(!frame.targets[folder])frame.targets[folder]={buttons:[],screens:[],numbers:[]};if(!frame.targets[folder][kind].includes(name))frame.targets[folder][kind].push(name);if(!frame.assets[kind].some(item=>item.value===folder+'/'+name))frame.assets[kind].push({value:folder+'/'+name,label:folder+' / '+name,target:folder,name,templates:[result.filename]});
   el('template-new-target').value='';el('template-new-name').value='';targets();el('template-target').value=folder;names();el('template-name').value=name;
   if(kind==='buttons'){const value=folder+'/'+name;let option=Array.from(el('button-name').options).find(o=>o.value===value);if(!option){option=document.createElement('option');option.value=value;el('button-name').append(option);}option.disabled=false;option.textContent=folder+' / '+name+' (custom template)';el('button-name').value=value;}
  }catch(error){status(error.message);}finally{busy=false;el('editor-capture').disabled=false;draw();}
 };
})();
