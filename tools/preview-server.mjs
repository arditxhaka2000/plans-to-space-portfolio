import http from 'node:http';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../server/wwwroot/',import.meta.url));
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.jpg':'image/jpeg','.png':'image/png','.svg':'image/svg+xml'};
http.createServer(async(req,res)=>{
 try{
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405).end();return;}
  const url=new URL(req.url,'http://localhost');
  const name=decodeURIComponent(url.pathname);
  if(name==='/'){res.writeHead(302,{Location:'/floors.html'}).end();return;}
  if(name!='/floors.html'&&!/^\/(assets|floors)\//.test(name)){res.writeHead(404).end();return;}
  const file=path.resolve(root,'.'+name);
  if(!file.startsWith(root)||!(await stat(file)).isFile()){res.writeHead(404).end();return;}
  res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','X-Content-Type-Options':'nosniff','X-Robots-Tag':'noindex, nofollow'});
  if(req.method==='HEAD')res.end();else createReadStream(file).pipe(res);
 }catch{res.writeHead(404).end();}
}).listen(5090,'127.0.0.1',()=>console.log('Read-only floor preview on 127.0.0.1:5090'));
