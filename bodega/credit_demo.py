"""Reglas de fiado para demostración local; nunca conecta a Supabase."""
from copy import deepcopy
from datetime import datetime,date,timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from bodega.repository import DataError


class CreditDemo:
    def _credit_init(self):
        if not hasattr(self,'credit_accounts'):
            self.credit_accounts=[];self.credit_charges=[];self.credit_payments=[];self.credit_operations={}

    def configure_credit(self,dni,name,limit,active):
        from bodega.credit import account_data
        self._credit_init();customer,value=account_data(dni,name,limit)
        found=next((x for x in self.credit_accounts if x['dni']==dni),None)
        if found:found.update(nombre=customer['nombre'],limite=str(value),activo=active)
        else:
            found={'id':len(self.credit_accounts)+1,'dni':dni,'nombre':customer['nombre'],'limite':str(value),'activo':active}
            self.credit_accounts.append(found)
        return {'cuenta_id':found['id']}

    def _credit_balance(self,vid):
        charge=next(x for x in self.credit_charges if x['venta_id']==vid)
        return Decimal(str(charge['importe']))-sum((Decimal(str(x['importe'])) for x in self.credit_payments if x['venta_id']==vid and not x.get('anulado_en')),Decimal(0))

    def credit_overview(self,query='',account=None):
        self._credit_init();accounts=[];charges=[]
        for a in self.credit_accounts:
            if query.casefold() not in (a['dni']+' '+a['nombre']).casefold():continue
            balance=sum((self._credit_balance(c['venta_id']) for c in self.credit_charges if c['cuenta_id']==a['id'] and self.headers[c['venta_id']-1]['estado']=='COMPLETADA'),Decimal(0))
            accounts.append({**a,'saldo':str(balance)})
        for c in self.credit_charges:
            if c['cuenta_id']==account:
                h=self.headers[c['venta_id']-1]
                charges.append({**deepcopy(c),'orden':f"VM-{h['id']:08d}",'fecha':h['fecha'],'estado':h['estado'],'saldo':str(self._credit_balance(h['id']))})
        vids={c['venta_id'] for c in charges}
        return {'cuentas':deepcopy(accounts[:100]),'cargos':charges[-250:][::-1],
                'abonos':deepcopy([x for x in self.credit_payments if x['venta_id'] in vids][-250:][::-1])}

    def credit_sale(self,op,items,account,due,total):
        self._credit_init();payload=(deepcopy(items),account,str(due),str(total))
        if op in self.credit_operations:
            old,result=self.credit_operations[op]
            if old!=payload:raise DataError('Operación reutilizada con otros datos')
            return deepcopy(result)
        a=next((x for x in self.credit_overview()['cuentas'] if x['id']==account),None)
        if not a:raise DataError('Cuenta de fiado no encontrada')
        if not a['activo']:raise DataError('Cuenta de fiado bloqueada')
        today=datetime.now(ZoneInfo('America/Lima')).date();deadline=date.fromisoformat(str(due))
        if deadline<today or deadline>today+timedelta(days=365):raise DataError('Fecha de fiado inválida')
        if Decimal(str(total))<=0 or Decimal(a['saldo'])+Decimal(str(total))>Decimal(a['limite']):raise DataError('Límite de fiado insuficiente')
        for c in self.credit_overview(account=account)['cargos']:
            if c['estado']=='COMPLETADA' and c['vencimiento']<str(today) and Decimal(c['saldo'])>0:raise DataError('El cliente tiene fiado vencido')
        result=self.sale(op,items,'Fiado',confirmed_total=total,customer={'dni':a['dni'],'nombre':a['nombre']})
        vid=result['venta_id'];self.credit_charges.append({'venta_id':vid,'cuenta_id':account,'importe':str(total),'vencimiento':str(due)})
        self.credit_operations[op]=(payload,deepcopy(result));return result

    def credit_payment(self,op,sale,amount,payment,reference='',entity=''):
        from bodega.checkout import payment_data
        from bodega.payments import confirmed_amount
        self._credit_init();value=confirmed_amount(amount);details=payment_data(payment,reference,entity)
        payload=(sale,str(value),payment,details)
        if op in self.credit_operations:
            old,result=self.credit_operations[op]
            if old!=payload:raise DataError('Operación reutilizada con otros datos')
            return deepcopy(result)
        if payment=='Fiado' or value<=0:raise DataError('Abono de fiado inválido')
        if self.headers[sale-1]['estado']!='COMPLETADA':raise DataError('La venta está anulada')
        if value>self._credit_balance(sale):raise DataError('El abono supera la deuda pendiente')
        if details['reference']:
            all_refs=[(h.get('medio_pago'),h.get('pago_entidad'),h.get('pago_referencia')) for h in self.headers]
            all_refs += [(a['medio_pago'],a.get('pago_entidad'),a.get('pago_referencia')) for a in self.credit_payments]
            if (payment,details['entity'],details['reference']) in all_refs:raise DataError('Referencia de pago ya utilizada')
        self.credit_payments.append({'id':op,'venta_id':sale,'importe':str(value),'medio_pago':payment,
            'pago_referencia':details['reference'],'pago_entidad':details['entity'],'anulado_en':None,'usuario_uid':'demo','creado_en':datetime.now(ZoneInfo('America/Lima')).isoformat()})
        result={'abono_id':op,'importe':str(value),'saldo_venta':str(self._credit_balance(sale))}
        self.credit_operations[op]=(payload,deepcopy(result));return result

    def credit_summary(self,since,until):
        self._credit_init();issued=Decimal(0);paid=Decimal(0);balance=Decimal(0);overdue=Decimal(0);series={}
        today=str(datetime.now(ZoneInfo('America/Lima')).date())
        for c in self.credit_charges:
            h=self.headers[c['venta_id']-1]
            if h['estado']!='COMPLETADA':continue
            remaining=self._credit_balance(c['venta_id']);balance+=remaining
            if c['vencimiento']<today:overdue+=remaining
            if str(since)<=h['fecha']<=str(until):
                issued+=Decimal(c['importe']);entry=series.setdefault(h['fecha'],{'fecha':h['fecha'],'credito':0.,'abonos':0.});entry['credito']+=float(c['importe'])
        for a in self.credit_payments:
            if a.get('anulado_en') or self.headers[a['venta_id']-1]['estado']!='COMPLETADA':continue
            day=a['creado_en'][:10]
            if str(since)<=day<=str(until):
                paid+=Decimal(a['importe']);entry=series.setdefault(day,{'fecha':day,'credito':0.,'abonos':0.});entry['abonos']+=float(a['importe'])
        return {'credito_periodo':str(issued),'abonos_periodo':str(paid),'cartera_actual':str(balance),'vencido_actual':str(overdue),'serie':[series[k] for k in sorted(series)]}

    def reverse_credit_payment(self,payment,reason):
        self._credit_init();a=next(x for x in self.credit_payments if x['id']==payment)
        if len(reason.strip())<3:raise DataError('Motivo requerido')
        if a.get('anulado_en') and a.get('motivo_anulacion')!=reason.strip():raise DataError('Operación reutilizada con otros datos')
        a.update(anulado_en=a.get('anulado_en') or datetime.now(ZoneInfo('America/Lima')).isoformat(),anulado_por='demo',motivo_anulacion=reason.strip())
        return {'abono_id':payment,'anulado':True}
