# Pitanja i odgovori za prezentaciju

Ovaj dokument služi kao brz podsetnik za pitanja koja mogu da se pojave na kraju prezentacije aplikacije.
Odgovori su formulisani kratko, jasno i u skladu sa PRD-om i trenutnim stanjem projekta.

## Kako da koristiš ovaj fajl

- Prvo nauči kratku priču o proizvodu.
- Zatim prođi kroz pitanja po kategorijama.
- Ne pokušavaj da odgovoriš tehnički previše duboko ako te ne pitaju direktno.
- Ako te uhvate na detalju koji nije deo MVP-a, reci da je to planirano za kasniju fazu ili da nije prioritet za demo.

## Kratka priča o aplikaciji

Platforma rešava zakazivanje konsultacija između studenata, profesora i asistenata na FON-u i ETF-u.
Glavna ideja je da student brzo pronađe profesora, vidi dostupne slotove, pošalje zahtev, dobije notifikaciju i vodi komunikaciju kroz aplikaciju, dok admin tim ima kontrolu nad korisnicima i dokumentima.

## 30-sekundni odgovor ako te pitaju: „Šta ova aplikacija radi?”

To je zatvorena univerzitetska platforma za zakazivanje konsultacija, chat, notifikacije, obradu zahteva za dokumente i admin nadzor.
Fokus je na tome da proces bude brz, pregledan i bez duplih termina, uz jasne role: student, asistent, profesor i admin.

## Najverovatnija pitanja i odgovori

### 1. Ko je ciljna grupa aplikacije?

Studenti FON-a i ETF-a, profesori, asistenti i studentska služba.
Student koristi platformu za pronalaženje i zakazivanje konsultacija, a osoblje za upravljanje terminima, komunikaciju i dokumentima.

### 2. Zašto je aplikacija zatvorena, a ne javna?

Zato što je namenjena samo aktivnim studentima i zaposlenima ova dva fakulteta.
Zatvorena registracija smanjuje zloupotrebu, olakšava kontrolu pristupa i usklađena je sa PRD-om.

### 3. Kako radi registracija?

Studenti mogu da se registruju samo sa dozvoljenim fakultetskim domenima.
Profesorske i admin naloge ne pravi javni korisnik, već ih kreira admin ili dolaze kroz seed/bulk import proces.

### 4. Zašto nema javnog sign-up-a?

Zato što bi javna registracija otvorila sistem van akademske zajednice.
Ovde je važnija kontrola identiteta nego rast korisnika.

### 5. Kako sprečavate prijavu sa pogrešnim email domenom?

Validacija domena je deo auth sloja i registracija prolazi samo ako email pripada dozvoljenim domenima.
Ako domen nije dozvoljen, zahtev se odbija pre kreiranja naloga.

### 6. Koje su uloge u sistemu?

STUDENT, ASISTENT, PROFESOR i ADMIN.
Svaka uloga ima jasno ograničen skup dozvola, a pristup se proverava na nivou endpoint-a i servisa.

### 7. Zašto je RBAC važan ovde?

Zato što nisu svi korisnici jednaki po pravima.
Student ne sme da vidi CRM beleške, asistent sme samo za dodeljene predmete, profesor ima širi pristup, a admin upravlja celim sistemom.

### 8. Kako sprečavate da student vidi tuđe podatke?

Svaki zaštićeni endpoint proverava identitet i ulogu korisnika.
Za osetljive podatke se dodatno proverava vlasništvo ili veza sa predmetom/terminom.

### 9. Zašto ste izabrali JWT autentifikaciju u V1?

Zato što je brža za implementaciju i dovoljna za MVP.
Keycloak je ostavljen za kasniju fazu kada se bude radila enterprise integracija.

### 10. Gde se čuva token?

Access token se drži u memoriji aplikacije, a refresh token u httpOnly cookie.
To je bezbednije nego localStorage jer smanjuje rizik od krađe tokena kroz XSS.

### 11. Zašto ne koristite localStorage?

Zato što je lokalno skladištenje lošije sa bezbednosne strane za auth tokene.
U ovom projektu je prioritet bezbednost sesije, pa je refresh token u cookie-ju, a access token u memoriji.

### 12. Kako funkcioniše zakazivanje termina?

Student bira profesora, vidi slobodne slotove, popunjava obavezna polja i šalje zahtev.
Zatim profesor ili asistent odobrava ili odbija zahtev, u zavisnosti od konfiguracije.

### 13. Kako sprečavate dupli booking?

Koristi se Redis lock pri zakazivanju.
Ideja je da samo jedan zahtev može da zauzme slot u datom trenutku, a ostali dobijaju konflikt i moraju da pokušaju ponovo.

### 14. Zašto je lock potreban ako već imate bazu?

Zato što baza sama ne rešava uvek trku između dva istovremena zahteva na nivou aplikacije.
Lock daje brzu i praktičnu zaštitu od dva paralelna korisnika koji kliknu isti slot.

### 15. Šta se dešava ako je profesor već bukiran?

Tada se aktivira waitlist.
Ako neko otkaže termin, sledeći student sa liste dobija ponudu za slobodan slot.

### 16. Kako radi notifikacioni sistem?

Sistem šalje in-app notifikacije, a za određene događaje i email/push obaveštenja.
Primeri su potvrda termina, odbijanje, otkazivanje, podsetnici i dokument request status.

### 17. Da li notifikacije dolaze u realnom vremenu?

Da, za ključne događaje je predviđen real-time pristup kroz WebSocket i push mehanizme.
Time korisnik dobija informaciju bez ručnog osvežavanja stranice.

### 18. Kako funkcioniše chat?

Chat je vezan za konkretan termin i koristi WebSocket za real-time poruke.
Time se komunikacija drži unutar konteksta termina i ne prelazi u opšti messenger.

### 19. Zašto je chat vezan za termin, a ne globalan?

Zato što je u ovom proizvodu komunikacija usko povezana sa konsultacijom.
Takav model je pregledniji, bezbedniji i lakši za nadzor.

### 20. Kako rešavate poverljive CRM beleške?

CRM beleške su dostupne samo osoblju i vezane su za profesora, asistenta ili predmet.
Student nema pristup tim podacima.

### 21. Šta je najveća razlika između profesora i asistenta?

Profesor ima širi pristup i može da upravlja svojim kalendarom i delegiranjem.
Asistent radi samo u okviru predmeta ili termina za koje je eksplicitno dodeljen.

### 22. Kako radi delegiranje asistentu?

Profesor može da prosledi zahtev asistentu, ali samo ako je asistent vezan za isti predmet.
To je kontrolisano RBAC pravilima i vezom preko predmeta.

### 23. Kako funkcioniše admin panel?

Admin može da upravlja korisnicima, vidi zahteve za dokumente, radi impersonaciju i prati audit log.
To je centralno mesto za studentsku službu.

### 24. Zašto postoji impersonacija?

Zbog dijagnostike i podrške.
Admin može da vidi iskustvo iz ugla drugog korisnika, ali uz obavezno logovanje te akcije i vidljiv indikator u UI.

### 25. Kako dokazujete da impersonacija nije zloupotrebljena?

Svaka takva akcija ide kroz audit log.
Time ostaje trag ko je, kada i koga impersonirao.

### 26. Zašto je potrebna audit evidencija?

Zato što se radi o akademskom sistemu sa osetljivim podacima.
Audit log pomaže kod bezbednosti, podrške i revizije.

### 27. Kako rade zahtevi za dokumente?

Student podnosi zahtev, admin ga pregleda, odobrava ili odbija i po potrebi unosi datum preuzimanja.
Student zatim dobija notifikaciju sa statusom i instrukcijom za preuzimanje.

### 28. Zašto su zahtevi za dokumente posebna funkcionalnost?

Zato što su to administrativni procesi koji nisu isto što i zakazivanje konsultacija.
Ipak, korisnički tok je sličan: zahtev, obrada, obaveštenje i završetak.

### 29. Koje su ključne prednosti ove platforme?

Manje ručnog rada, manje duplih termina, bolja preglednost za studente i bolja kontrola za osoblje.
Uz to, sve je centralizovano na jednom mestu.

### 30. Zašto ste izabrali Next.js App Router?

Zato što omogućava dobru podelu na server i client komponente, bolji organizacioni model i lakše skaliranje UI slojeva.
U ovom tipu aplikacije to prirodno odgovara i statičnim i interaktivnim delovima.

### 31. Zašto koristite TanStack Query?

Zato što server state u ovakvoj aplikaciji mora da bude keširan, osvežavan i usklađen sa real-time promenama.
To je bolje nego ručno upravljanje fetch logikom kroz mnogo useEffect poziva.

### 32. Zašto je Zod bitan?

Zod daje jasnu validaciju na klijentu i smanjuje broj loših zahteva pre slanja na backend.
To poboljšava UX i usklađuje frontend sa backend šemama.

### 33. Zašto je backend asinhron?

Zato što sistem radi sa mnogo I/O operacija: baza, Redis, notifikacije, WebSocket i background taskovi.
Async pristup je prirodan i efikasan za takvo opterećenje.

### 34. Zašto SQLAlchemy i ne raw SQL?

ORM pristup daje bolju održivost, čitljivost i sigurnost od direktnog raw SQL-a.
Takođe je lakše održavati konzistentan model kroz ceo projekat.

### 35. Zašto su potrebni background taskovi?

Ne želiš da endpoint blokira dok šalje email ili obrađuje veći posao.
Zato se te stvari prebacuju u Celery taskove.

### 36. Zašto Redis u arhitekturi?

Redis se koristi za lockove, keš i real-time/queue scenarije.
Posebno je koristan kada treba brzo koordinisati konkurentne akcije.

### 37. Zašto PostgreSQL?

Zato što aplikacija ima relacione entitete, mnogo veza između korisnika, termina, predmeta i notifikacija.
PostgreSQL je dobar izbor za takvu strukturu podataka.

### 38. Kako obezbeđujete da je sve u skladu sa PRD-om?

PRD koristiš kao source of truth za poslovna pravila.
Implementacija prati uloge, tokove i ograničenja koja su tamo definisana.

### 39. Šta je trenutno najjači deo aplikacije?

Najjači deo je kompletan tok: pretraga profesora, pregled profila, zakazivanje, notifikacije, chat i admin obrada.
To je već dovoljno za realan end-to-end scenario.

### 40. Šta još nije deo MVP-a?

Stvari poput Keycloak SSO, analytics dashboard-a i eventualne mobile aplikacije su planirane za kasnije.
Ako te to pitaju, reci da su namerno ostavljene za V2.

## Pitanja koja mogu da zvuče nezgodno

### 41. Šta ako vas pitaju zašto niste napravili sve funkcionalnosti iz PRD-a?

Zato što je ovo MVP, ne finalni enterprise proizvod.
Prvo se završavaju ključni tokovi koji nose vrednost, a napredne stvari idu u narednu fazu.

### 42. Šta ako vas pitaju zašto nema mobilne aplikacije?

Zato što je PWA dovoljan za prvu verziju.
To pokriva mobilni osećaj korišćenja bez dodatnog održavanja posebne aplikacije.

### 43. Šta ako pitaju da li sistem može da skalira?

Arhitektura je postavljena tako da podrži odvajanje backend servisa, background taskova, Redis sloja i frontend aplikacije.
Za ovaj nivo opterećenja to je više nego dovoljno, a kasnije se može širiti.

### 44. Šta ako pitaju šta je najveći rizik?

Najveći rizik su real-time tokovi i konkurentne izmene termina.
Zato su lockovi, testovi i jasna pravila za zakazivanje toliko važni.

### 45. Šta ako pitaju kako testirate sistem?

Koriste se integration i E2E scenariji za ključne tokove: login, booking, notifikacije, chat i admin akcije.
To je najbitnije jer testira stvarno korisničko ponašanje, ne samo pojedinačne funkcije.

### 46. Šta ako pitaju da li ste imali bugove sa dvostrukim zakazivanjem?

Možeš da kažeš da je to bio očekivan rizik i da je rešavan kroz Redis lock i testove za konkurentne zahteve.
Važno je da pokažeš da problem razumeš, a ne da tvrdiš da ga nikad nije bilo.

### 47. Šta ako pitaju zašto je frontend toliko veliki?

Zato što je aplikacija feature-rich i treba joj mnogo posebnih ekrana po ulozi.
To je normalno za produktivan admin/staff/student sistem, a ne za mali landing page.

### 48. Šta ako pitaju gde je glavna poslovna vrednost?

Glavna vrednost je u smanjenju administrativnog haosa i boljoj organizaciji konsultacija.
Student brže dolazi do termina, a osoblje ima kontrolu i trag aktivnosti.

### 49. Šta ako pitaju da li je ovo samo „CRUD aplikacija”?

Nije samo CRUD.
Postoje real-time notifikacije, chat, rezervacije sa lockovima, role-based pristup, admin audit i više različitih tokova.

### 50. Šta je najbolji završni odgovor ako traže zaključak?

Ovo je zatvorena, sigurnija i organizovanija platforma koja digitalizuje konsultacije i studentske administrativne tokove.
U MVP-u smo fokus stavili na funkcije koje daju najveću praktičnu vrednost i koje mogu stabilno da se demonstriraju.

## Kratke rečenice koje možeš bukvalno da koristiš

- „Ovo je zatvorena platforma za FON i ETF, ne javni servis.”
- „Prvo smo rešili ključni tok, a napredne stvari ostavljamo za V2.”
- „RBAC je ključan jer različite uloge imaju različite nivoe pristupa.”
- „Redis lock koristimo da sprečimo duple rezervacije.”
- „Chat i notifikacije su vezani za konkretan termin, ne kao opšti messenger.”
- „Admin ima audit trag za sve osetljive akcije.”

## Ako te pitaju nešto van ovoga

Vrati razgovor na tri stvari:

1. Koju ulogu korisnik ima.
2. Da li je to deo MVP-a ili V2.
3. Kako je rešeno bezbedno i pregledno.

Ako želiš, mogu da ti napravim i posebnu verziju ovog fajla u formatu „kratak odgovor / duži odgovor / opaske za komisiju”.