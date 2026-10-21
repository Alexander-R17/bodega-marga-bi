"""Demostración aislada en memoria. Datos sintéticos; nunca llama al servicio cloud."""
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from bodega.repository import DataError

ROOT = Path(__file__).resolve().parents[1]


class DemoRepository:
    def __init__(self):
        self.products = pd.read_csv(ROOT/"data/productos_demo.csv", dtype={"codigo":str}).to_dict("records")
        self.categories, self.suppliers = [], []
        for p in self.products:
            for field, collection in [("categoria",self.categories),("proveedor",self.suppliers)]:
                name=p.pop(field)
                found=next((x for x in collection if x["nombre"]==name), None)
                if not found:
                    found={"id":len(collection)+1,"nombre":name}; collection.append(found)
                p[field+"_id"]=found["id"]
        raw=pd.read_csv(ROOT/"data/ventas_demo.csv", dtype={"codigo":str})
        self.sales=[]; self.headers=[]; self.movements=[]; self.batches=[]; self.staging={}
        self.events=[]; self.predictions=[]; self.operations={}; self.decisions=[]
        for ticket, group in raw.groupby("ticket",sort=False):
            vid=len(self.headers)+1
            total=sum(float(r.cantidad*r.precio_unitario-r.descuento) for r in group.itertuples())
            self.headers.append({"id":vid,"fecha":group.iloc[0].fecha,"medio_pago":group.iloc[0].medio_pago,
                "origen":"HISTORICO","ticket_externo":ticket,"estado":"COMPLETADA","total":total})
            for r in group.to_dict("records"):
                p=next(p for p in self.products if p["codigo"]==r["codigo"])
                self._line(vid,p,r["fecha"],r["cantidad"],r["precio_unitario"],r["costo_unitario"],r["descuento"],r["medio_pago"],"HISTORICO")

    def _line(self,vid,p,date,qty,price,cost,disc,payment,origin):
        self.sales.append({"id_detalle":len(self.sales)+1,"venta_id":vid,"fecha":date,"producto_id":p["id"],
            "codigo":p["codigo"],"nombre":p["nombre"],"categoria":next(c["nombre"] for c in self.categories if c["id"]==p["categoria_id"]),
            "proveedor":next(c["nombre"] for c in self.suppliers if c["id"]==p["proveedor_id"]),
            "cantidad":qty,"precio_unitario":price,"costo_unitario":cost,"descuento":disc,
            "ingreso":round(qty*price-disc,2),"margen_bruto":round(qty*(price-cost)-disc,2),
            "medio_pago":payment,"origen":origin})

    def table(self,name):
        if name == "bodega_tiempo":
            from bodega.bi import facts
            return facts(pd.DataFrame(self.sales))[["fecha", "anio", "mes", "dia_semana_num"]].drop_duplicates().rename(columns={"dia_semana_num":"dia_semana"}).assign(dia=lambda x:x.fecha.dt.day)
        if name == "bodega_v_cubo_ventas":
            from bodega.bi import facts, cube
            return cube(facts(self.table("bodega_v_ventas")), ["periodo_mes", "categoria", "medio_pago"])
        mapping={"bodega_productos":self.products,"bodega_categorias":self.categories,"bodega_proveedores":self.suppliers,
            "bodega_v_ventas":[s for s in self.sales if self.headers[s["venta_id"]-1]["estado"]=="COMPLETADA"],
            "bodega_ventas":self.headers,"bodega_movimientos":self.movements,"bodega_lotes":self.batches,
            "bodega_eventos":self.events,"bodega_predicciones":self.predictions,"bodega_reposiciones":self.decisions}
        return pd.DataFrame(deepcopy(mapping[name]))

    def _operation(self,op,payload):
        if op in self.operations:
            old,result=self.operations[op]
            if old!=payload: raise DataError("Operación reutilizada con otros datos")
            return deepcopy(result)
        return None

    def sale(self,op,items,payment):
        payload=(deepcopy(items),payment)
        result=self._operation(op,payload)
        if result: return result
        if len({x["producto_id"] for x in items})!=len(items) or not items: raise DataError("Cantidad inválida")
        for x in items:
            p=next(p for p in self.products if p["id"]==x["producto_id"])
            if not p["activo"] or x["cantidad"]<=0 or not 0<=x["descuento"]<=x["cantidad"]*p["precio"]: raise DataError("Cantidad inválida")
            if p["stock"]<x["cantidad"]: raise DataError("Stock insuficiente")
        vid=len(self.headers)+1; now=datetime.now(ZoneInfo("America/Lima"));date=now.date().isoformat(); total=0
        for x in items:
            p=next(p for p in self.products if p["id"]==x["producto_id"])
            self._line(vid,p,date,x["cantidad"],p["precio"],p["costo"],x["descuento"],payment,"POS")
            self.sales[-1]["fecha_hora"]=now.isoformat()
            p["stock"]-=x["cantidad"]; total+=self.sales[-1]["ingreso"]
            self.movements.append({"id":len(self.movements)+1,"producto_id":p["id"],"tipo":"VENTA", "variacion":-x["cantidad"],"stock_resultante":p["stock"]})
        self.headers.append({"id":vid,"fecha":date,"fecha_hora":now.isoformat(),"medio_pago":payment,"origen":"POS","estado":"COMPLETADA","total":round(total,2)})
        result={"venta_id":vid,"total":round(total,2)}; self.operations[op]=(payload,result)
        return result

    def movement(self,op,product_id,kind,quantity,cost,reason):
        payload=(product_id,kind,quantity,cost,reason); result=self._operation(op,payload)
        if result: return result
        p=next(p for p in self.products if p["id"]==product_id)
        delta=quantity-p["stock"] if kind=="AJUSTE" else (-quantity if kind=="MERMA" else quantity)
        if not delta: raise DataError("No hay cambios")
        new=p["stock"]+delta
        if new<0: raise DataError("Stock insuficiente")
        if kind=="ENTRADA": p["costo"]=round((p["stock"]*p["costo"]+quantity*cost)/new,2)
        p["stock"]=new
        self.movements.append({"id":len(self.movements)+1,"producto_id":product_id,"tipo":kind,"variacion":delta,"stock_resultante":new,"motivo":reason})
        result={"stock":new,"costo":p["costo"]}; self.operations[op]=(payload,result); return result

    def save_product(self,product):
        p=deepcopy(product)
        for field,collection in [("categoria",self.categories),("proveedor",self.suppliers)]:
            name=p.pop(field)
            found=next((x for x in collection if x["nombre"]==name),None)
            if not found: found={"id":len(collection)+1,"nombre":name}; collection.append(found)
            p[field+"_id"]=found["id"]
        if p.get("id"):
            old=next(x for x in self.products if x["id"]==p["id"]); old.update(p)
        else:
            if any(x["codigo"]==p["codigo"] for x in self.products): raise DataError("Código duplicado")
            p.update(id=len(self.products)+1,stock=0); self.products.append(p)
        return {"producto_id":p["id"]}

    def create_batch(self,batch_id,name,sha,records):
        existing=next((b for b in self.batches if b["hash_archivo"]==sha),None)
        if existing: return {"lote_id":existing["id"],"estado":existing["estado"]}
        self.batches.append({"id":batch_id,"nombre":name,"hash_archivo":sha,"filas":len(records),"estado":"VALIDADO"})
        self.staging[batch_id]=deepcopy(records)
        return {"lote_id":batch_id,"estado":"VALIDADO"}

    def process_batch(self,batch_id):
        b=next(b for b in self.batches if b["id"]==batch_id)
        if b["estado"]=="PROCESADO": return {"filas":b["filas"],"estado":"PROCESADO"}
        rows=self.staging[batch_id]
        if any(h.get("ticket_externo") in {r["ticket"] for r in rows} for h in self.headers):
            raise DataError("Ticket histórico ya existe")
        df=pd.DataFrame(rows)
        for ticket,group in df.groupby("ticket",sort=False):
            vid=len(self.headers)+1; total=0
            for r in group.to_dict("records"):
                p=next(p for p in self.products if p["codigo"]==r["codigo"])
                self._line(vid,p,r["fecha"],r["cantidad"],float(r["precio_unitario"]),float(r["costo_unitario"]),float(r["descuento"]),r["medio_pago"],"HISTORICO")
                total+=self.sales[-1]["ingreso"]
            self.headers.append({"id":vid,"fecha":group.iloc[0].fecha,"medio_pago":group.iloc[0].medio_pago,
                "origen":"HISTORICO","ticket_externo":ticket,"estado":"COMPLETADA","total":round(total,2)})
        b["estado"]="PROCESADO"; return {"filas":b["filas"],"estado":"PROCESADO"}

    def annul(self,op,vid,reason):
        payload=(vid,reason); result=self._operation(op,payload)
        if result: return result
        h=self.headers[vid-1]
        if h["estado"]=="COMPLETADA" and h["origen"]=="POS":
            for line in self.sales:
                if line["venta_id"]==vid:
                    p=next(p for p in self.products if p["id"]==line["producto_id"]); p["stock"]+=line["cantidad"]
        h["estado"]="ANULADA"; result={"venta_id":vid,"estado":"ANULADA"}; self.operations[op]=(payload,result); return result

    def save_forecast(self,records):
        for r in records:
            old=next((p for p in self.predictions if all(p[k]==r[k] for k in ["producto_id","fecha","corte"])),None)
            if old: old.update(r)
            else: self.predictions.append({"id":len(self.predictions)+1,**r})
        return {"filas":len(records)}

    def event(self,event,detail="",session_id=None,page=""):
        self.events.append({"id":len(self.events)+1,"evento":event,"detalle":detail,
            "fecha_hora":datetime.now(ZoneInfo("America/Lima")).isoformat(),"usuario_uid":"demo",
            "sesion_id":session_id,"pagina":page})

    def decision(self,op,product_id,units,decision,reason,context):
        payload=(product_id,units,decision,reason,context); result=self._operation(op,payload)
        if result:return result
        self.decisions.append({"id":op,"producto_id":product_id,"unidades":units,"decision":decision,
            "motivo":reason,"contexto":context})
        result={"id":op,"decision":decision};self.operations[op]=(payload,result);return result
