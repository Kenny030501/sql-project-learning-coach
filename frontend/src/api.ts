export async function api(path:string,body?:unknown,method="POST"){
 const options:RequestInit=body===undefined?{}:{method,headers:{"Content-Type":"application/json","X-Coach-Request":"1"},body:JSON.stringify(body)};
 const r=await fetch(path,options);const data=await r.json();if(!r.ok)throw Error(data.error||data.detail||"请求失败");return data;
}
export function download(name:string,data:unknown){
 const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));
 const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
