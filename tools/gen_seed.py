import json, os, datetime as dt
WIB = dt.timezone(dt.timedelta(hours=7))
def ts(s):
    d = dt.datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M").replace(tzinfo=WIB)
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
W = {'identity':20,'repeat':15,'need':15,'layout':15,'qty':10,'timeline':10,'location':5,'budget':10}
NAMES = {'GIL':'Gilang','ADI':'Adi','AND':'Andri','HEN':'Pak Hendy','NOV':'Novi','REV':'Revita','YUL':'Yulianti','DIN':'Dini','END':'Enda','EVI':'Evi','IVA':'Ivan','YOP':'Yopi','WEL':'Welly'}
enq, req = {}, {}
def E(key, no, cust, contact, phone, email, line, typ, product, loc, qty, rec, upd, status, stage, kyc, source, log, contacted=None, **x):
    region, seller = no.split('-')[1], no.split('-')[2]
    k = {a: True for a in kyc.split()}
    sc = max(0, sum(W[a] for a in k) - 10 * x.get('redFlags', 0))
    d = dict(enqNo=no, received=ts(rec), lastUpdate=ts(upd), source=source, customer=cust, contact=contact, phone=phone, email=email,
             line=line, type=typ, product=product, location=loc, qty=qty, region=region, seller=seller, firstOwner=seller,
             status=status, stage=stage, redFlags=0, kyc=k, score=sc, intakeScore=x.pop('intake', sc),
             log=[dict(t=ts(t), who=NAMES.get(w, w), text=txt) for t, w, txt in log])
    if contacted: d['contactedAt'] = ts(contacted)
    d.update(x)
    d['tier'] = 'P' if d.get('priceCheck') else ('A' if sc >= 70 else 'B' if sc >= 40 else 'C')
    enq[key] = d
def Q(tpl, rev, *lines):
    ls = [dict(item=i, qty=q, price=p) for i, q, p in lines]
    return dict(tpl=tpl, rev=rev, lines=ls, total=sum(l['qty'] * l['price'] for l in ls))
def R(key, ek, dept, title, status, sent, log, acc=None, due=None, ret=None, urgent=False, nudges=0, **x):
    e = enq[ek]
    d = dict(enqId=ek, enqNo=e['enqNo'], dept=dept, seller=e['seller'], region=e['region'], title=title, urgent=urgent, status=status,
             sentAt=ts(sent), nudges=nudges, log=[dict(t=ts(t), who=NAMES.get(w, w), text=txt) for t, w, txt in log])
    if acc: d['acceptedAt'] = ts(acc)
    if due: d['due'] = ts(due)
    if ret: d['returnedAt'] = ts(ret)
    d.update(x); req[key] = d

# ---- SBY ----
E('e-sby-0014','ENQ-SBY-ADI-261111-0014','PT Bumi Konstruksi (sample)','Bpk. Rudi, Site Manager','0812-5550-0114','rudi@bumikonstruksi.example','Modular','Project','Modular office, 6 units','Gresik','6','11-11 13:10','11-11 13:10','New','New','identity need layout qty timeline','Central',
  [('11-11 13:10','System','Created from email to the shared enquiry mailbox. Index number ENQ-SBY-ADI-261111-0014.')], dateNeeded='Jan 2027', pricingDeadline='18 Nov 2026')
E('e-sby-0013','ENQ-SBY-AND-261110-0013','PT Papua Mandiri (sample)','Ibu Yohana, Procurement','0813-5550-0113','yohana@papuamandiri.example','Container','Project','Site camp, 40ft office x 4','Jayapura','4','11-10 15:00','11-10 15:00','New','New','identity need qty timeline location budget','Central',
  [('11-10 15:00','System','Created from email to the shared enquiry mailbox.')], dateNeeded='Feb 2027')
E('e-sby-0009','ENQ-SBY-ADI-261104-0009','CV Nusa Logistik (sample)','Bpk. Hendra, Owner','0811-5550-0109','hendra@nusalogistik.example','Container','Retail','40ft dry container x 20 (sale)','Gresik','20','11-04 09:20','11-11 15:00','Ongoing','Quote sent','identity repeat need qty timeline location','Central',
  [('11-11 15:00','ADI','Follow-up: customer is comparing with one competitor. proof: WA screenshot'),('11-10 14:10','ADI','Follow-up: customer asked for 5% discount on 20 units. proof: email'),('11-09 10:30','ADI','Quotation rev.2 (Sale) sent: Rp 1,029,000,000.'),('11-04 11:45','ADI','First contact by Call: confirmed 20 units, delivery to Gresik.')],
  contacted='11-04 11:45', quote=Q('Sale',2,('40ft Dry container, cargo-worthy',20,48500000),('Lockbox and forklift pockets',20,1750000),('Delivery within the city, per unit',20,1200000)), dateNeeded='Dec 2026')
E('e-sby-0006','ENQ-SBY-ADI-261028-0006','PT Samudra Bali (sample)','Ibu Kadek Ayu, Owner','0812-5550-0106','kadek@samudrabali.example','Modification','Retail','Container cafe, 2 x 20ft, glass front, AC','Canggu, Bali','2','10-28 10:12','11-11 08:40','Ongoing','Drafter','identity repeat need layout qty timeline location','Central',
  [('11-10 08:40','Drafter','Drafter accepted the request, due 13 Nov.'),('11-07 14:05','ADI','Request sent to Drafter: cafe modification 2 x 20ft.'),('11-06 16:30','ADI','Follow-up: call with Ibu Kadek, budget not shared yet. proof: call log'),('10-28 13:15','ADI','First contact by WhatsApp. proof: WA screenshot')],
  contacted='10-28 13:15', intake=65, dateNeeded='Jan 2027', pricingDeadline='20 Nov 2026')
E('e-sby-0012','ENQ-SBY-ADI-261109-0012','Hotel Ubud Lestari (sample)','Bpk. Made','0817-5550-0112','','Container','Retail','20ft reefer rental','Ubud, Bali','','11-09 10:00','11-09 14:00','Contacted','KYC','identity need location','WhatsApp',
  [('11-09 14:00','ADI','First contact by WhatsApp: asked for quantity and start date. proof: WA screenshot')], contacted='11-09 14:00')
E('e-sby-0010','ENQ-SBY-ADI-261105-0010','PT Lombok Agro (sample)','Ibu Sri','0818-5550-0110','sri@lombokagro.example','Container','Retail','20ft dry container x 4 (rental)','Mataram, NTB','4','11-05 08:50','11-05 16:20','Ongoing','Quote sent','identity need qty location','Direct email',
  [('11-05 16:20','ADI','Quotation rev.1 (Rental) sent: Rp 7,600,000.'),('11-05 10:05','ADI','First contact by Email.')],
  contacted='11-05 10:05', quote=Q('Rental',1,('20ft Dry container rental, per month',4,1900000)))
E('e-sby-0008','ENQ-SBY-ADI-261102-0008','(no company given)','gmail user','','hargakontainer@gmail.example','Container','Retail','"Harga kontainer?"','','','11-02 09:00','11-02 11:00','No response','Price-check','need','Central',
  [('11-02 11:00','ADI','Catalog price range sent. Asked for company and quantity. No reply.')], contacted='11-02 11:00', priceCheck=True, redFlags=1)
E('e-sby-0011','ENQ-SBY-GIL-261106-0011','PT Timur Sanitasi (sample)','Bpk. Yoseph','0821-5550-0111','yoseph@timursanitasi.example','Modular','Project','Toilet module x 10','Kupang, NTT','10','11-06 13:30','11-11 09:00','Ongoing','Estimator','identity need layout qty timeline location budget','Direct email',
  [('11-11 09:00','GIL','Follow-up: customer confirmed budget ceiling. proof: email'),('11-06 16:00','GIL','Request sent to Estimator: toilet module x 10.'),('11-06 14:40','GIL','First contact by Call.')], contacted='11-06 14:40', dateNeeded='Jan 2027')
E('e-sby-0004','ENQ-SBY-AND-261020-0004','PT Flobamora Jaya (sample)','Bpk. Markus','0822-5550-0104','markus@flobamorajaya.example','Container','Project','Office container x 4 with AC','Kupang, NTT','4','10-20 09:00','11-09 11:30','Won','Production','identity need layout qty timeline location budget','Central',
  [('11-09 11:30','Trucking','Trucking accepted the delivery request.'),('11-06 11:00','Purchasing','Purchasing handed back: vendor PO for AC units issued.'),('11-03 15:00','Sales Support','Work order opened, kickoff held, minutes shared.'),('10-31 10:00','GIL','PO package approved by RM.')],
  contacted='10-20 10:30', quote=Q('Sale',3,('20ft Office container, standard',4,68000000),('Delivery within the city, per unit',4,1200000)), po=dict(drawing=True,quote=True,match=True,terms=True,timeline=True,payment=True))
E('e-sby-0007','ENQ-SBY-AND-261103-0007','PT Dewata Tambang (sample)','Bpk. Wayan','0823-5550-0107','wayan@dewatatambang.example','Container','Project','Mess hall, 40ft x 3','Sumbawa, NTB','3','11-03 10:10','11-06 09:00','Contacted','KYC','identity need qty location','Central',
  [('11-06 09:00','AND','Follow-up: waiting for the site layout from the customer.'),('11-03 15:30','AND','First contact by Call.')], contacted='11-03 15:30')
E('e-sby-0003','ENQ-SBY-GIL-261022-0003','PT Sorong Maritim (sample)','Bpk. Daniel','0852-5550-0103','daniel@sorongmaritim.example','Container','Retail','40ft reefer x 4','Sorong','4','10-22 10:00','11-05 10:00','Lost','Quote sent','identity need qty timeline location','Central',
  [('11-05 10:00','GIL','Status: Lost (Price). Competitor was 8% lower.')], contacted='10-22 11:00', lossReason='Price', quote=Q('Sale',1,('40ft Reefer container',4,165000000)))
E('e-sby-0002','ENQ-SBY-GIL-261019-0002','PT Bali Resor Indah (sample)','Ibu Putu','0853-5550-0102','putu@baliresor.example','Modular','Retail','Modular office 6 x 3 m, 6 units','Nusa Dua, Bali','6','10-19 09:30','10-30 14:00','Won','BAST signed','identity repeat need layout qty timeline location budget','Direct email',
  [('10-30 14:00','GIL','Stage moved to BAST signed.')], contacted='10-19 10:15', quote=Q('Sale',2,('Modular office unit 6 x 3 m',6,82000000)), po=dict(drawing=True,quote=True,match=True,terms=True,timeline=True,payment=True))
E('e-sby-0015','ENQ-SBY-ADI-261112-0015','CV Gili Bahari (sample)','Ibu Lina','0819-5550-0115','lina@gilibahari.example','Container','Retail','20ft office container','Lombok Utara','1','11-12 08:40','11-12 08:40','New','New','identity need qty location','WhatsApp',
  [('11-12 08:40','ADI','Enquiry logged from WhatsApp.')])
E('e-sby-0016','ENQ-SBY-GIL-261112-0016','PT Surabaya Cold Chain (sample)','Bpk. Anton','0816-5550-0116','anton@sbycoldchain.example','Container','Retail','20ft reefer x 2 (rental)','Surabaya','2','11-12 08:10','11-12 09:10','Contacted','KYC','identity repeat need qty location','Direct email',
  [('11-12 09:10','GIL','First contact by Call: rental for 6 months from December.')], contacted='11-12 09:10')
# ---- BPN ----
E('e-bpn-0003','ENQ-BPN-HEN-261030-0003','PT Borneo Karya (sample)','Bpk. Syahrul','0811-5550-0203','syahrul@borneokarya.example','Container','Project','Workshop container 40ft x 6','Balikpapan','6','10-30 10:00','11-10 09:00','Ongoing','Estimator','identity need layout qty timeline location','Central',
  [('11-10 09:00','Estimator','Estimator accepted the request, due 13 Nov.')], contacted='10-30 11:10')
E('e-bpn-0007','ENQ-BPN-NOV-261109-0007','PT Mahakam Energi (sample)','Ibu Rina','0812-5550-0207','rina@mahakamenergi.example','Modular','Project','Mess camp, 40 persons','Samarinda','','11-09 09:00','11-11 16:00','Ongoing','Drafter','identity need layout timeline location budget','Central',
  [('11-11 16:00','NOV','Request sent to Drafter: mess camp layout.'),('11-09 10:20','NOV','First contact by Call.')], contacted='11-09 10:20')
E('e-bpn-0006','ENQ-BPN-REV-261015-0006','PT Kutai Baja (sample)','Bpk. Arif','0813-5550-0206','arif@kutaibaja.example','Modification','Project','Tool store container x 3, steel frame','Bontang','3','10-15 09:00','11-03 10:00','Won','Production','identity repeat need layout qty timeline location budget','Central',
  [('11-03 10:00','Purchasing','Purchasing accepted the vendor PO request.')], contacted='10-15 10:00', quote=Q('Sale',2,('20ft Office container, standard',3,68000000)), po=dict(drawing=True,quote=True,match=True,terms=True,timeline=True,payment=True))
# ---- JKT ----
E('e-jkt-0005','ENQ-JKT-EVI-261103-0005','PT Citra Bangun (sample)','Bpk. Fajar','0811-5550-0305','fajar@citrabangun.example','Modular','Project','Site office, 12 units, 2 levels','Bekasi','12','11-03 09:00','11-05 10:00','Ongoing','Drafter','identity need layout qty timeline location','Central',
  [('11-05 10:00','Drafter','Drafter accepted the request, due 11 Nov.')], contacted='11-03 11:30')
E('e-jkt-0002','ENQ-JKT-IVA-261101-0002','PT Segar Laut (sample)','Ibu Maya','0812-5550-0302','maya@segarlaut.example','Container','Retail','Reefer 20ft with genset package','Muara Baru','2','11-02 08:30','11-06 09:00','Ongoing','Estimator','identity need qty location','Direct email',
  [('11-06 09:00','Estimator','Estimator accepted the request, due 10 Nov.')], contacted='11-02 13:40')
E('e-jkt-0001','ENQ-JKT-WEL-261012-0001','PT Karya Cikarang (sample)','Bpk. Dedi','0813-5550-0301','dedi@karyacikarang.example','Container','Retail','40ft dry container x 6','Cikarang','6','10-12 10:00','11-10 10:00','Won','Production','identity repeat need qty timeline location budget','Central',
  [('11-10 10:00','Trucking','Trucking accepted the delivery request.')], contacted='10-12 11:00', quote=Q('Sale',1,('40ft Dry container, cargo-worthy',6,48500000)), po=dict(drawing=True,quote=True,match=True,terms=True,timeline=True,payment=True))
E('e-jkt-0004','ENQ-JKT-END-261028-0004','PT Tangerang Logam (sample)','Ibu Nia','0815-5550-0304','nia@tangeranglogam.example','Modular','Project','Modular office 6 x 3 m, 4 units','Tangerang','4','10-28 09:00','11-11 10:00','Won','WO / Kickoff','identity need layout qty timeline location budget','Central',
  [('11-11 10:00','DIN','PO package approved by RM. Work order requested.')], contacted='10-28 10:10', quote=Q('Sale',2,('Modular office unit 6 x 3 m',4,82000000)), po=dict(drawing=True,quote=True,match=True,terms=True,timeline=True,payment=True))
E('e-jkt-0003','ENQ-JKT-YOP-261027-0003','PT Depok Prima (sample)','Bpk. Agus','0816-5550-0303','agus@depokprima.example','Container','Retail','20ft office container x 2','Depok','2','10-27 13:00','11-04 11:00','Lost','Quote sent','identity need qty location','WhatsApp',
  [('11-04 11:00','YOP','Status: Lost (Lead time). Customer needed delivery in 5 days.')], contacted='10-27 15:10', lossReason='Lead time', quote=Q('Sale',1,('20ft Office container, standard',2,68000000)))

# ---- requests ----
R('r01','e-sby-0006','Drafter','Cafe modification 2 x 20ft, glass front, AC','accepted','11-07 14:05',[('11-10 08:40','Drafter','Accepted by Drafter. Due in 3 business days.'),('11-07 14:05','ADI','Request sent to Drafter.')],acc='11-10 08:40',due='11-13 17:00')
R('r02','e-sby-0014','Drafter','Modular office 6 units, layout needed tomorrow for pricing','pending','11-12 09:00',[('11-12 09:00','ADI','Request sent to Drafter. Urgent, waiting for RM approval.')],urgent=True)
R('r03','e-sby-0011','Estimator','Toilet module x 10, unit price including delivery to Kupang','sent','11-06 16:00',[('11-11 09:05','GIL','Nudge sent: please confirm status.'),('11-10 08:00','System','One business day with no feedback. Flagged to the RM.'),('11-09 10:00','GIL','Nudge sent: please confirm status.'),('11-09 08:00','System','No accept after 4 business hours. Reminder sent to Estimator.'),('11-06 16:00','GIL','Request sent to Estimator.')],nudges=2)
R('r04','e-sby-0004','Purchasing','Vendor PO: AC units x 8','returned','11-03 09:00',[('11-06 11:00','Purchasing','Handed back: vendor PO issued, delivery 14 Nov.'),('11-03 13:00','Purchasing','Accepted by Purchasing.'),('11-03 09:00','AND','Request sent to Purchasing.')],acc='11-03 13:00',due='11-06 17:00',ret='11-06 11:00')
R('r05','e-sby-0004','Trucking','Delivery to Kupang, 4 units by vessel','accepted','11-09 10:00',[('11-09 11:30','Trucking','Accepted by Trucking. Vessel ETA 18 Nov.'),('11-09 10:00','AND','Request sent to Trucking.')],acc='11-09 11:30',due='11-18 17:00')
R('r06','e-sby-0013','Branch','Site visit and survey, Jayapura','sent','11-10 15:30',[('11-12 09:05','AND','Nudge sent: mohon konfirmasi jadwal survey lokasi.'),('11-11 15:30','System','One business day with no feedback. Flagged to the RM.'),('11-11 10:30','System','No accept after 4 business hours. Reminder sent to Branch.'),('11-10 15:30','AND','Request sent to Branch.')],nudges=1)
R('r07','e-sby-0009','Depo','Stock check: 20 x 40ft dry, cargo-worthy','returned','11-04 11:00',[('11-04 16:00','Depo','Handed back: 18 units ready, 2 more by 20 Nov.'),('11-04 12:00','Depo','Accepted by Depo.'),('11-04 11:00','ADI','Request sent to Depo.')],acc='11-04 12:00',due='11-05 17:00',ret='11-04 16:00')
R('r08','e-sby-0012','Depo','Reefer 20ft unit check, 2 units for rental','sent','11-11 13:00',[('11-11 13:00','ADI','Request sent to Depo.')])
R('r09','e-sby-0004','Sales Support','Work order and kickoff meeting','returned','11-02 09:00',[('11-03 15:00','Sales Support','Handed back: work order opened, minutes of meeting shared, 5 action items.'),('11-02 10:00','Sales Support','Accepted by Sales Support.'),('11-02 09:00','GIL','Work order and kickoff requested after RM approval.')],acc='11-02 10:00',due='11-04 17:00',ret='11-03 15:00')
R('r10','e-sby-0009','Estimator','Price for lockbox and forklift pockets option','returned','11-05 09:00',[('11-07 10:00','Estimator','Handed back: Rp 1,750,000 per unit.'),('11-05 15:00','Estimator','Accepted by Estimator.'),('11-05 09:00','ADI','Request sent to Estimator.')],acc='11-05 15:00',due='11-09 17:00',ret='11-07 10:00')
R('r11','e-sby-0007','Estimator','Budget price for mess hall, 40ft x 3','sent','11-11 09:30',[('11-11 14:30','System','No accept after 4 business hours. Reminder sent to Estimator.'),('11-11 09:30','AND','Request sent to Estimator.')])
R('r12','e-bpn-0003','Estimator','Workshop container 40ft x 6, price','accepted','11-09 14:00',[('11-10 09:00','Estimator','Accepted by Estimator.'),('11-09 14:00','HEN','Request sent to Estimator.')],acc='11-10 09:00',due='11-13 17:00')
R('r13','e-bpn-0007','Drafter','Mess camp layout, 40 persons','sent','11-11 16:00',[('11-11 16:00','NOV','Request sent to Drafter.')])
R('r14','e-bpn-0006','Purchasing','Vendor PO: steel frame','accepted','11-03 09:00',[('11-03 10:00','Purchasing','Accepted by Purchasing. Budget proposal in review.'),('11-03 09:00','REV','Request sent to Purchasing.')],acc='11-03 10:00',due='11-09 17:00')
R('r15','e-jkt-0005','Drafter','Site office 12 units, stacked 2 levels','accepted','11-04 15:00',[('11-05 10:00','Drafter','Accepted by Drafter.'),('11-04 15:00','EVI','Request sent to Drafter.')],acc='11-05 10:00',due='11-11 17:00')
R('r16','e-jkt-0002','Estimator','Reefer 20ft with genset package, price','accepted','11-05 11:00',[('11-06 09:00','Estimator','Accepted by Estimator.'),('11-05 11:00','IVA','Request sent to Estimator.')],acc='11-06 09:00',due='11-10 17:00')
R('r17','e-jkt-0001','Trucking','Truck to Cikarang, 6 units','accepted','11-10 09:00',[('11-10 10:00','Trucking','Accepted by Trucking.'),('11-10 09:00','WEL','Request sent to Trucking.')],acc='11-10 10:00',due='11-14 17:00')
R('r18','e-jkt-0004','Sales Support','Work order and kickoff meeting','accepted','11-11 10:00',[('11-11 11:00','Sales Support','Accepted by Sales Support.'),('11-11 10:00','DIN','Work order and kickoff requested after RM approval.')],acc='11-11 11:00',due='11-13 17:00')

cat = {
 'c01': dict(item='40ft Dry container, cargo-worthy', category='Dry 40ft', mode='Sale', price=48500000, unit='per unit'),
 'c02': dict(item='20ft Dry container, cargo-worthy', category='Dry 20ft', mode='Sale', price=27500000, unit='per unit'),
 'c03': dict(item='20ft Reefer container', category='Reefer 20ft', mode='Sale', price=115000000, unit='per unit'),
 'c04': dict(item='40ft Reefer container', category='Reefer 40ft', mode='Sale', price=165000000, unit='per unit'),
 'c05': dict(item='20ft Office container, standard', category='Modification', mode='Sale', price=68000000, unit='per unit'),
 'c06': dict(item='Modular office unit 6 x 3 m', category='Modular', mode='Sale', price=82000000, unit='per unit'),
 'c07': dict(item='20ft Dry container rental, per month', category='Dry 20ft', mode='Rental', price=1900000, unit='per unit per month'),
 'c08': dict(item='20ft Reefer rental, per month', category='Reefer 20ft', mode='Rental', price=9500000, unit='per unit per month'),
 'c09': dict(item='Delivery within the city, per unit', category='Service', mode='Service', price=1200000, unit='per unit, one way'),
}
meta = {'config': dict(demoNow='2026-11-12T10:00:00+07:00', note='Demo clock for the sample data. Remove this field to run on the live clock.')}
out = dict(enquiries=enq, requests=req, catalog=cat, meta=meta)
json.dump(out, open('../model/seed.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
writes = []
for col, docs in out.items():
    os.makedirs(f'../model/seed_docs/{col}', exist_ok=True)
    for k, d in docs.items():
        p = f'../model/seed_docs/{col}/{k}.json'
        json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
        writes.append(dict(op='set', collection=col, doc_id=k, file_path=p))
json.dump(writes, open('../model/writes.json', 'w'))
print(len(enq), len(req), len(cat), len(writes))
