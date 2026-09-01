\set ON_ERROR_STOP on

-- Public event records sampled from prod.dump on 2026-09-01. Production users
-- and credentials are deliberately excluded; the demo user below is synthetic.
-- Run only against a fresh local/test database.

BEGIN;

INSERT INTO events (
  title, end_time, venue_name, city, description, image_url,
  organizer_name, category, ticket_url, popularity_counter,
  ticket_purchase_note, address, price_from, price_to, source_url,
  start_time, lat, lng
)
VALUES
  (
    'IKI Ėjimo varžybos | Kaunas 2026', NULL,
    'A. Smetonos al. 4, Kaunas', 'Kaunas',
    'Rudens pradžios tradicija – „IKI Ėjimo varžybos“ Kaune. Nemokama registracija.',
    'https://images.avilys.app/events/12280.jpg',
    'Event by walk15 and Kauno miesto savivaldybės visuomenės sveikatos biuras',
    'Wellness', 'https://ikiejimovarzybos.lt/', 2584,
    NULL, NULL, NULL, NULL,
    'https://www.facebook.com/events/1548748219558690/',
    '2026-09-05 11:00:00', 54.87549, 23.9657
  ),
  (
    'Tarptautinis jurginų festivalis VDU Botanikos sode Kaune', NULL,
    'Ž. E. Žilibero g. 4, 46324 Kaunas, Lithuania', 'Kaunas',
    'VDU Botanikos sodas Kaune kviečia į tarptautinį jurginų festivalį.',
    'https://images.avilys.app/events/26857.jpg',
    'Event by VDU Botanikos sodas Kaune', NULL, NULL, 1938,
    NULL, NULL, NULL, NULL,
    'https://www.facebook.com/events/1578788393593799/',
    '2026-09-03 13:00:00', 54.87109, 23.91211
  ),
  (
    'SOLO ANSAMBLIS | KAUNAS', '2026-09-05 22:00:00',
    'Kauno jachtklubas', 'Kaunas',
    'Kasmetinis jausmų ir kojų masažas Kaune. Durys 18:00, muzika 20:00.',
    'https://images.avilys.app/events/21363.jpg',
    'Event by Solo Ansamblis, DAMN GOOD and Marina Live', NULL,
    'https://www.bilietai.lt/renginiai/MQLU6ZPNZZ/solo-ansamblis-kaunas/?shop_provider=damngood',
    425, NULL, 'Kauno Jachtklubas', 40, 40,
    'https://www.facebook.com/events/28201852516082575/',
    '2026-09-05 20:00:00', 54.88528109091, 24.022501940907
  ),
  (
    'GIEDRĖ | Žalgirio arena | Kaunas', '2027-03-20 21:40:00',
    'Žalgirio arena', 'Kaunas',
    'Dainininkė Giedrė pirmą kartą kviečia klausytojus į solinį koncertą Kauno „Žalgirio“ arenoje.',
    'https://images.avilys.app/events/23716.jpg',
    'Event by Giedrė and Bilietai.lt', 'Music',
    'https://www.bilietai.lt/renginiai/X5BKBWEXLF/giedre-zalgirio-arena-kaunas',
    328, NULL, 'Kauno Žalgirio arena', 39, 74,
    'https://www.facebook.com/events/1767417517932786/',
    '2027-03-20 20:00:00', 54.890431176266, 23.914940357208
  ),
  (
    'TrekTours Costline Trek: Piejūras pārgājiens''26', NULL,
    'Smiltynės g. 13B, Klaipėda, 93100 Klaipėdos m. sav., Lithuania', 'Klaipėda',
    '19. septembrī notiks līdz šim lielākais TrekTours pārgājiens.',
    'https://images.avilys.app/events/20436.jpg',
    'Event by TrekTours Latvia', 'Wellness', 'https://bit.ly/4dyUY9B',
    1900, NULL, NULL, NULL, NULL,
    'https://www.facebook.com/events/2151305855718621/',
    '2026-09-19 07:00:00', 55.705778798853, 21.110568557539
  ),
  (
    'Vagelis. Aikštelė | Švyturio arena, Klaipėda', NULL,
    'ŠVYTURIO ARENA', 'Klaipėda',
    'Gabrielius Vagelis kviečia į vieną didžiausių savo karjeros koncertų.',
    'https://images.avilys.app/events/10370.jpg',
    'Event by Ventures Events, Gabrielius Vagelis and ŠVYTURIO ARENA', NULL,
    'https://www.bilietai.lt/lit/renginiai/koncertai/klaipeda-vagelis-aikstele-494490/',
    1342, NULL, 'Dubysos g. 10-1', NULL, NULL,
    'https://www.facebook.com/events/1577848591008711/',
    '2026-12-11 20:00:00', 55.68737, 21.15182
  ),
  (
    'Braziliškas pilvo drenažas Klaipėda', NULL,
    'Klaipeda, Lietuva', 'Klaipėda',
    'Braziliškas pilvo masažas – technika adaptuota mūsų laikams.',
    'https://images.avilys.app/events/9849.jpg',
    'Event by Karina Mik Masažo Akademija', NULL, NULL,
    55, NULL, NULL, 200, NULL,
    'https://www.facebook.com/events/1598682937818040/',
    '2026-11-19 09:30:00', 55.7, 21.1333
  ),
  (
    'International Dog Shows in Palanga/ Tarptautinės šunų parodos Palangoje (CACIB)', NULL,
    'Palangos kempingas Compensa', 'Palanga',
    'Lietuvos kinologų draugija Palangos kempinge organizuos tris tarptautines šunų parodas.',
    'https://images.avilys.app/events/22861.jpg',
    'Event by LKD - Lietuvos kinologų draugija. Lithuanian Kennel Club', NULL, NULL,
    326, NULL, 'Klaipėdos pl. 33I', NULL, NULL,
    'https://www.facebook.com/events/2500690160396119/',
    '2026-09-25 10:00:00', 55.876478471458, 21.066241264343
  ),
  (
    'IMANY | PALANGA', NULL,
    'Palangos Koncertų Salė', 'Palanga',
    'Viena ryškiausių šiuolaikinės soul ir pop muzikos atlikėjų Imany koncertuos Palangoje.',
    'https://images.avilys.app/events/22770.jpg',
    'Event by Bravo events and Palangos Koncertų Salė', 'Music',
    'https://kakava.lt/renginys/imany/12595', 315,
    NULL, 'Vytauto gatvė 43', NULL, NULL,
    'https://www.facebook.com/events/1562555545490110/',
    '2027-04-23 20:00:00', 55.915620828, 21.063577296666
  ),
  (
    'Markas Žukauskas “Viskas Tvarkoj” Stand up Panevėžys', NULL,
    'Desperado77', 'Panevėžys',
    'Ketvirtoji Marko Žukausko solo stand-up programa „Viskas Tvarkoj“.',
    'https://images.avilys.app/events/25595.jpg',
    'Event by Markas Žukauskas and Desperado77', 'Comedy',
    'https://tickets.paysera.com/lt-LT/event/markas-zukauskas-viskas-tvarkoj-stand-up-panevezys-33ee',
    2, NULL, 'Nemuno g. 77', NULL, NULL,
    'https://www.facebook.com/events/1528232738384255/',
    '2026-09-09 20:00:00', 55.730653156002, 24.340230442822
  ),
  (
    'Transcendentinis Garso Patyrimas - Gongų Maudynės Šiauliuose', NULL,
    'Tilžės gatvė 118, Šiauliai, AK Pilates studija', 'Šiauliai',
    'Kosmiška garso odisėja su gongais, Himalajų skambančiais dubenėliais ir šamanišku būgnu.',
    'https://images.avilys.app/events/26107.jpg',
    'Transcendentinis Garsas', 'Health', NULL,
    1574, NULL, NULL, NULL, NULL,
    'https://www.facebook.com/events/1435761107003289/',
    '2026-09-25 18:00:00', 55.92792, 23.30908
  ),
  (
    '#ŠiauliaiGroja scena | Šiaulių dienos 790', NULL,
    'Prisikėlimo Aikštė Šiauliai', 'Šiauliai',
    'Šiauliai švenčia ypatingą sukaktį – 790-ąjį miesto gimtadienį.',
    'https://images.avilys.app/events/26546.jpg',
    'Koncertų salė „Saulė“', 'Music', NULL,
    423, NULL, NULL, NULL, NULL,
    'https://www.facebook.com/events/1569563978214260/',
    '2026-09-11 21:00:00', 55.932853717802, 23.31649489792
  ),
  (
    'Free Finga Tour | Šiauliai', NULL,
    'HAVANA, Šiauliai', 'Šiauliai',
    'Pirmasis Free Finga ir grupės turas, peržengiantis Lietuvos sienas.',
    'https://images.avilys.app/events/25938.jpg',
    'Žiauru', NULL, 'https://kakava.lt/renginys/free-finga-tour/12640/26618',
    335, NULL, NULL, NULL, NULL,
    'https://www.facebook.com/events/1367162532013268/',
    '2026-11-21 20:00:00', 55.92892, 23.31812
  ),
  (
    'VILNIAUS DIENOS 2026', NULL,
    'Senamiestis', 'Vilnius',
    'Vilnius pasitinka rudenį kupinas miesto pulso, muzikos, spalvų ir susitikimų.',
    'https://images.avilys.app/events/18225.jpg',
    'Event by Vilniaus miesto savivaldybė and Vilniaus kultūros centras', NULL, NULL,
    5560, NULL, NULL, NULL, NULL,
    'https://www.facebook.com/events/1757426902304644/',
    '2026-09-04 08:00:00', 54.6833333333, 25.2833333333
  ),
  (
    'VILNIUS IS MY CITY 2026', NULL,
    'Bernardinų Sodas', 'Vilnius',
    'Tarptautinės bendruomenės šventė, kviečianti kartu švęsti Vilniaus žmones.',
    'https://images.avilys.app/events/27026.jpg',
    'Event by Go Vilnius and International House Vilnius', NULL, NULL,
    2188, NULL, NULL, NULL, NULL,
    'https://www.facebook.com/events/2083419982569199/',
    '2026-09-05 11:00:00', 54.684405484411, 25.295495046303
  ),
  (
    'SOLO ANSAMBLIS | VILNIUS', '2026-09-09 22:00:00',
    'Vasaros Terasa', 'Vilnius',
    'Kasmetinis jausmų ir kojų masažas Vilniuje. Durys 18:00, muzika 20:00.',
    'https://images.avilys.app/events/20161.jpg',
    'Event by Solo Ansamblis, DAMN GOOD and Vasaros Terasa', NULL,
    'https://www.bilietai.lt/renginiai/XYBRJ4PF6C/solo-ansamblis-vilnius/?shop_provider=damngood',
    1317, NULL, 'Vasaros terasa', 45, 45,
    'https://www.facebook.com/events/1015039650932824/',
    '2026-09-09 20:00:00', 54.682254768704, 25.279734134674
  ),
  (
    'PUTOOOJA''26 - Craft gėrimų festivalis', '2026-09-12 22:00:00',
    'Dūmų fabrikas', 'Vilnius',
    '36 bravorai iš viso pasaulio, 140 alaus rūšių ir neribotas degustavimas.',
    'https://qqpltdizdaxvcxslnzkr.supabase.co/storage/v1/object/public/event-images/b4510350-fa37-4e0a-bf75-e866b234f78e.jfif',
    'Dūmų fabrikas', 'Festivalis',
    'https://www.dumufabrikas.lt/event/putoooja-26-1636/register',
    1009, NULL, 'Dūmų g. 5, Vilnius', 70, 110,
    'https://www.dumufabrikas.lt/putoja',
    '2026-09-11 17:00:00', NULL, NULL
  ),
  (
    'Vilnius Jazz 2026: Dainius Pulauskas Group (LT)', '2026-10-14 22:00:00',
    'Vilniaus senasis teatras', 'Vilnius',
    'Dainius Pulauskas Group švenčia savo kūrybinės veiklos trisdešimtmetį.',
    'https://www.bilietai.lt/i/height=1009/images/ec0590d2-be7b-43ac-9069-2f2da16b9ddd',
    'VšĮ Vilniaus džiazo festivalis', NULL,
    'https://www.bilietai.lt/renginiai/ABFBFJSYOI/vilnius-jazz-2026-dainius-pulauskas-group-lt',
    14, 'Durys atidaromos: ~18:30', 'J. Basanavičiaus g. 13, Vilnius', 25, 40,
    'https://www.bilietai.lt/renginiai/ABFBFJSYOI/vilnius-jazz-2026-dainius-pulauskas-group-lt',
    '2026-10-14 19:00:00', NULL, NULL
  );

INSERT INTO users (
  email, password_hash, first_name, last_name, favorite_event_ids
)
VALUES (
  'demo@avilys.example.com',
  '$2b$10$ku72VnKP/JOk.qMB1Muu7.h7CxoUo2KsdBX033WKu1zAne8WBbyjy',
  'Demo',
  'User',
  ARRAY(
    SELECT id
    FROM events
    WHERE source_url IN (
      'https://www.facebook.com/events/1548748219558690/',
      'https://www.facebook.com/events/1562555545490110/',
      'https://www.bilietai.lt/renginiai/ABFBFJSYOI/vilnius-jazz-2026-dainius-pulauskas-group-lt'
    )
    ORDER BY id
  )
);

COMMIT;
