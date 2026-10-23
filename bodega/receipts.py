"""Ticket de venta interno en PDF. No implementa emisión tributaria SUNAT."""
from io import BytesIO
from xml.sax.saxutils import escape
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal


def money(value):
    return f"S/ {Decimal(str(value or 0)):,.2f}"


def receipt_pdf(data):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    output=BytesIO()
    normal=ParagraphStyle('normal',fontName='Helvetica',fontSize=8.5,leading=11,spaceAfter=4)
    small=ParagraphStyle('small',parent=normal,fontSize=7,leading=9)
    title=ParagraphStyle('title',parent=normal,fontName='Helvetica-Bold',fontSize=14,leading=18,alignment=1)
    center=ParagraphStyle('center',parent=normal,alignment=1)
    def para(value,style=normal): return Paragraph(escape(str(value)),style)
    flow=[para('BODEGA MARGA',title),para('TICKET INTERNO',center),para(data['orden'],center)]
    if data.get('estado')=='ANULADA': flow.append(para('VENTA ANULADA',title))
    raw=data.get('fecha_hora')
    try:
        stamp=datetime.fromisoformat(str(raw).replace('Z','+00:00')).astimezone(ZoneInfo('America/Lima'))
        date=stamp.strftime('%d/%m/%Y %H:%M')
    except (ValueError,TypeError): date=data.get('fecha','Sin fecha')
    flow.extend([para(f"Fecha: {date}"),para(f"Cliente: {data.get('cliente_nombre') or 'Consumidor final'}")])
    if data.get('cliente_dni'): flow.append(para(f"DNI: {data['cliente_dni']}"))
    flow.append(Spacer(1,5))
    rows=[[para('Cant.',small),para('Producto',small),para('P. unit.',small),para('Importe',small)]]
    for item in data['items']:
        rows.append([para(item['cantidad'],small),para(f"{item['nombre']}\n{item['codigo']}",small),
            para(money(item['precio_unitario']),small),para(money(item['ingreso']),small)])
    table=Table(rows,colWidths=[21,96,43,46],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1),
        ('RIGHTPADDING',(0,0),(-1,-1),1),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#173b32'))]))
    flow.extend([table,Spacer(1,6),para(f"Subtotal: {money(data['subtotal'])}"),
        para(f"Descuento: {money(data['descuento'])}"),para(f"TOTAL: {money(data['total'])}",title),
        para(f"Medio de pago: {data['medio_pago']}")])
    if data.get('pago_referencia'):
        flow.extend([para(f"Entidad: {data.get('pago_entidad','')}"),para(f"Operación: {data['pago_referencia']}")])
    flow.append(para('Pago confirmado manualmente en caja.' if data.get('pago_confirmado_en') else 'Sin verificación de pago registrada.',small))
    if data.get('origen')=='HISTORICO': flow.append(para('Venta procedente del historial importado.',small))
    if data.get('datos_reconstruidos'):
        flow.append(para('Venta anterior a los tickets: descripción reconstruida con el catálogo disponible.',small))
    flow.extend([Spacer(1,7),para('No es un comprobante de pago tributario. No sustituye una boleta o factura electrónica SUNAT.',small)])
    def footer(canvas,document):
        canvas.setFont('Helvetica',6)
        canvas.drawCentredString(40*mm,6*mm,f"{data['orden']} - Página {document.page}")
    needed=sum(item.wrap(80*mm-20,10000)[1]+item.getSpaceBefore()+item.getSpaceAfter() for item in flow)+44
    page_height=max(100*mm,min(210*mm,needed))
    doc=SimpleDocTemplate(output,pagesize=(80*mm,page_height),rightMargin=10,leftMargin=10,
        topMargin=12,bottomMargin=14,title=f"Ticket interno {data['orden']}",author="Bodega Marga")
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()


def receipt_panel(repo,vid):
    import streamlit as st
    data=repo.receipt(vid)
    if data.get('estado')=='ANULADA': st.warning('Venta anulada. La reimpresión conserva ese estado.')
    st.markdown(f"**Ticket interno {data['orden']}**")
    st.caption('PDF para entregar o imprimir. La emisión de boletas electrónicas SUNAT requiere una integración adicional.')
    st.download_button('Descargar ticket PDF',receipt_pdf(data),f"ticket_{data['orden']}.pdf",'application/pdf',
        key=f"download_ticket_{vid}",on_click='ignore')

