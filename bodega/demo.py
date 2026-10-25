"""Demostración aislada en memoria. Datos sintéticos; nunca llama al servicio cloud."""
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
import pandas as pd
from bodega.repository import DataError
from bodega.credit_demo import CreditDemo

ROOT = Path(__file__).resolve().parents[1]


class DemoRepository(CreditDemo):
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
        self.events=[]; self.predictions=[]; self.operations={}; self.decisions=[]; self.tickets={}
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

    def clear_cache(self):
        pass

    def recent_table(self,name,limit=250):
        data=self.table(name)
        return data.tail(limit).iloc[::-1].copy()

    def table(self,name,*,since=None,until=None):
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
        data=pd.DataFrame(deepcopy(mapping[name]))
        if not data.empty and "fecha" in data:
            dates=pd.to_datetime(data.fecha)
            if since: data=data.loc[dates>=pd.Timestamp(since)]
            if until: data=data.loc[pd.to_datetime(data.fecha)<=pd.Timestamp(until)]
        return data

    def _operation(self,op,payload):
        if op in self.operations:
            old,result=self.operations[op]
            if old!=payload: raise DataError("Operación reutilizada con otros datos")
            return deepcopy(result)
        return None

    def sale(self,op,items,payment,*,confirmed_total=None,customer=None,reference="",entity=""):
        from decimal import Decimal
        from bodega.payments import confirmed_amount
        amount=confirmed_amount(confirmed_total)
        from bodega.checkout import customer_data,payment_data,order_number
        customer=customer_data(customer); details=payment_data(payment,reference,entity)
        payload=(deepcopy(items),payment,deepcopy(customer),details)
        result=self._operation(op,payload)
        if result:
            if Decimal(str(result["total"])) != amount: raise DataError("El total cambió. Revisa el carrito y confirma el pago nuevamente")
            return result
        if details['reference'] and any(h.get('medio_pago')==payment and h.get('pago_referencia')==details['reference'] and h.get('pago_entidad')==details['entity'] for h in self.headers):
            raise DataError('Referencia de pago ya utilizada')
        if details['reference'] and any(a['medio_pago']==payment and a.get('pago_referencia')==details['reference'] and a.get('pago_entidad')==details['entity'] for a in getattr(self,'credit_payments',[])):
            raise DataError('Referencia de pago ya utilizada')
        if len({x["producto_id"] for x in items})!=len(items) or not items: raise DataError("Cantidad inválida")
        for x in items:
            p=next(p for p in self.products if p["id"]==x["producto_id"])
            if not p["activo"] or x["cantidad"]<=0 or not 0<=x["descuento"]<=x["cantidad"]*p["precio"]: raise DataError("Cantidad inválida")
            if p["stock"]<x["cantidad"]: raise DataError("Stock insuficiente")
        expected=sum((Decimal(str(next(p for p in self.products if p["id"]==x["producto_id"])["precio"]))*x["cantidad"]-Decimal(str(x["descuento"])) for x in items),Decimal(0))
        if expected != amount: raise DataError("El total cambió. Revisa el carrito y confirma el pago nuevamente")
        vid=len(self.headers)+1; now=datetime.now(ZoneInfo("America/Lima"));date=now.date().isoformat(); total=0
        for x in items:
            p=next(p for p in self.products if p["id"]==x["producto_id"])
            self._line(vid,p,date,x["cantidad"],p["precio"],p["costo"],x["descuento"],payment,"POS")
            self.sales[-1]["fecha_hora"]=now.isoformat()
            p["stock"]-=x["cantidad"]; total+=self.sales[-1]["ingreso"]
            self.movements.append({"id":len(self.movements)+1,"producto_id":p["id"],"tipo":"VENTA", "variacion":-x["cantidad"],"stock_resultante":p["stock"],"usuario_uid":"demo"})
        self.headers.append({"id":vid,"fecha":date,"fecha_hora":now.isoformat(),"medio_pago":payment,"origen":"POS","estado":"COMPLETADA","total":round(total,2),"usuario_uid":"demo", "pago_confirmado_en":now.isoformat(),"pago_confirmado_por":"demo","pago_confirmado_total":float(amount),
            'cliente_dni':customer['dni'] or None,'cliente_nombre':customer['nombre'] or None,
            'pago_referencia':details['reference'] or None,'pago_entidad':details['entity'] or None,'pago_validacion':'MANUAL_CAJA'})
        if payment=='Fiado':
            self.headers[-1].update(pago_confirmado_en=None,pago_confirmado_por=None,pago_confirmado_total=None,pago_validacion='CREDITO_FIADO')
        self.tickets[vid]=self.receipt(vid)
        self.tickets[vid].pop('datos_reconstruidos',None)
        result={"venta_id":vid,"total":round(total,2),'orden':order_number(vid)}; self.operations[op]=(payload,result)
        return result

    def receipt(self,vid):
        from bodega.checkout import order_number
        h=next((x for x in self.headers if x['id']==vid),None)
        if h is None: raise DataError('Venta no encontrada')
        if vid in self.tickets:
            result={**deepcopy(self.tickets[vid]),'estado':h['estado']}
            if h['medio_pago']=='Fiado' and hasattr(self,'credit_charges'):
                charge=next((c for c in self.credit_charges if c['venta_id']==vid),None)
                if charge:
                    balance=self._credit_balance(vid)
                    result.update(fiado_vencimiento=charge['vencimiento'],fiado_abonado=str(Decimal(str(charge['importe']))-balance),fiado_saldo=str(balance if h['estado']=='COMPLETADA' else Decimal(0)))
            return result
        items=[{'codigo':s['codigo'],'nombre':s['nombre'],'cantidad':s['cantidad'],
                'precio_unitario':s['precio_unitario'],'descuento':s['descuento'],'ingreso':s['ingreso']}
               for s in self.sales if s['venta_id']==vid]
        return {**deepcopy(h),'venta_id':vid,'orden':order_number(vid),'items':items,
            'cliente_nombre':h.get('cliente_nombre') or 'Consumidor final',
            'subtotal':round(sum(s['cantidad']*s['precio_unitario'] for s in items),2),
            'descuento':round(sum(s['descuento'] for s in items),2),'datos_reconstruidos':True}

    def search_sales(self,since,until,query='',status='TODOS',payment='Todos',page=0,size=25):
        from bodega.checkout import order_number
        if since>until or page<0 or not 1<=size<=100: raise DataError('Filtros de ventas inválidos')
        result=[]; query=query.strip().casefold()
        for header in self.headers:
            h=deepcopy(header);h['orden']=order_number(h['id'])
            h.setdefault('cliente_nombre','Consumidor final');h['cliente_nombre']=h['cliente_nombre'] or 'Consumidor final'
            h.setdefault('cliente_dni',None);h.setdefault('pago_referencia',None)
            if not str(since)<=str(h['fecha'])[:10]<=str(until): continue
            if status!='TODOS' and h['estado']!=status: continue
            if payment!='Todos' and h['medio_pago']!=payment: continue
            if query and not any(query in str(h.get(k) or '').casefold() for k in ['id','orden','cliente_dni','cliente_nombre','ticket_externo']): continue
            result.append(h)
        result.sort(key=lambda h:(str(h['fecha']),str(h.get('fecha_hora') or h['fecha']),h['id']),reverse=True)
        return {'total':len(result),'rows':result[page*size:(page+1)*size]}

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
        if h['medio_pago']=='Fiado' and any(a['venta_id']==vid and not a.get('anulado_en') for a in getattr(self,'credit_payments',[])):
            raise DataError('Anula primero los abonos del fiado y concilia la devolución')
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
