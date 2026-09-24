# Normalização das Regiões Administrativas

As 35 Regiões Administrativas do DF aparecem com nomenclaturas diferentes em
cada fonte. Este documento registra o mapeamento adotado, como ele foi obtido e
onde ele é verificado.

## 1. Chave canônica

O projeto usa o **código romano da RA** (`RA-I` … `RA-XXXV`) como chave em todo
o modelo. Ele foi escolhido em vez do nome porque:

* é publicado pelo GDF no campo `ra_codigo` da malha oficial;
* aparece dentro das próprias planilhas da SSP-DF (`RA XX - ÁGUAS CLARAS`);
* não muda quando o nome muda.

O IBGE não usa esse código — usa o `subdistrict_id` (ex.: `53001080515`). A
ponte entre os dois é o seed [`dbt/seeds/region_name_map.csv`](../dbt/seeds/region_name_map.csv).

## 2. Como o mapeamento foi construído

1. **Malha do GDF** — 35 RAs com `ra_codigo`, `ra_cira` (número) e `ra_nome`,
   do serviço ArcGIS do IBRAM/ONDA-DF.
2. **Subdistritos do IBGE** — 35 registros de
   `/localidades/municipios/5300108/subdistritos`.
3. **Casamento por normalização** — remoção de acentos, pontuação e caixa.
   34 dos 35 casaram exatamente.
4. **Revisão manual do caso restante**, confirmado pelo número da RA nas duas
   fontes.

O seed é gerado uma vez e versionado. **O join nunca é feito por nome em tempo
de execução** — casar região por string é exatamente o erro que este projeto se
recusa a cometer.

## 3. A única divergência de nome

| Fonte | Grafia |
|---|---|
| GDF (IBRAM/ONDA-DF) | `SOL NASCENTE E POR DO SOL` |
| IBGE (subdistritos) | `Sol Nascente/Pôr do Sol` |

São a mesma RA: ambas as fontes a identificam como RA XXXII. A equivalência
está registrada no seed com `name_match_method = manual_reviewed` e a
justificativa no campo `note`.

Todos os outros 34 nomes casam após normalização — as diferenças são só de
acentuação e caixa (`CEILÂNDIA` ↔ `Ceilândia`, `AGUA QUENTE` ↔ `Água Quente`).

## 4. Nome exibido

A interface usa a grafia do **IBGE**, que já vem em caixa mista correta
(`Núcleo Bandeirante`, `Sudoeste/Octogonal`, `SIA`). A grafia do GDF fica
preservada em `dim_region.region_name_gdf` para auditoria.

## 5. Tabela completa

| RA | Nº | Nome (IBGE) | Nome (GDF) | Subdistrito IBGE | Método |
|---|---|---|---|---|---|
| `RA-I` | 1 | Plano Piloto | PLANO PILOTO | `53001080506` | normalized_exact |
| `RA-II` | 2 | Gama | GAMA | `53001080507` | normalized_exact |
| `RA-III` | 3 | Taguatinga | TAGUATINGA | `53001080508` | normalized_exact |
| `RA-IV` | 4 | Brazlândia | BRAZLÂNDIA | `53001080509` | normalized_exact |
| `RA-V` | 5 | Sobradinho | SOBRADINHO | `53001080510` | normalized_exact |
| `RA-VI` | 6 | Planaltina | PLANALTINA | `53001080511` | normalized_exact |
| `RA-VII` | 7 | Paranoá | PARANOÁ | `53001080512` | normalized_exact |
| `RA-VIII` | 8 | Núcleo Bandeirante | NÚCLEO BANDEIRANTE | `53001080514` | normalized_exact |
| `RA-IX` | 9 | Ceilândia | CEILÂNDIA | `53001080515` | normalized_exact |
| `RA-X` | 10 | Guará | GUARÁ | `53001080516` | normalized_exact |
| `RA-XI` | 11 | Cruzeiro | CRUZEIRO | `53001080517` | normalized_exact |
| `RA-XII` | 12 | Samambaia | SAMAMBAIA | `53001080518` | normalized_exact |
| `RA-XIII` | 13 | Santa Maria | SANTA MARIA | `53001080525` | normalized_exact |
| `RA-XIV` | 14 | São Sebastião | SÃO SEBASTIÃO | `53001080530` | normalized_exact |
| `RA-XV` | 15 | Recanto das Emas | RECANTO DAS EMAS | `53001080520` | normalized_exact |
| `RA-XVI` | 16 | Lago Sul | LAGO SUL | `53001080523` | normalized_exact |
| `RA-XVII` | 17 | Riacho Fundo | RIACHO FUNDO | `53001080513` | normalized_exact |
| `RA-XVIII` | 18 | Lago Norte | LAGO NORTE | `53001080521` | normalized_exact |
| `RA-XIX` | 19 | Candangolândia | CANDANGOLÂNDIA | `53001080519` | normalized_exact |
| `RA-XX` | 20 | Águas Claras | ÁGUAS CLARAS | `53001080536` | normalized_exact |
| `RA-XXI` | 21 | Riacho Fundo II | RIACHO FUNDO II | `53001080541` | normalized_exact |
| `RA-XXII` | 22 | Sudoeste/Octogonal | SUDOESTE/OCTOGONAL | `53001080535` | normalized_exact |
| `RA-XXIII` | 23 | Varjão | VARJÃO | `53001080543` | normalized_exact |
| `RA-XXIV` | 24 | Park Way | PARK WAY | `53001080542` | normalized_exact |
| `RA-XXV` | 25 | SCIA | SCIA | `53001080534` | normalized_exact |
| `RA-XXVI` | 26 | Sobradinho II | SOBRADINHO II | `53001080544` | normalized_exact |
| `RA-XXVII` | 27 | Jardim Botânico | JARDIM BOTÂNICO | `53001080540` | normalized_exact |
| `RA-XXVIII` | 28 | Itapoã | ITAPOÃ | `53001080538` | normalized_exact |
| `RA-XXIX` | 29 | SIA | SIA | `53001080533` | normalized_exact |
| `RA-XXX` | 30 | Vicente Pires | VICENTE PIRES | `53001080537` | normalized_exact |
| `RA-XXXI` | 31 | Fercal | FERCAL | `53001080539` | normalized_exact |
| `RA-XXXII` | 32 | Sol Nascente/Pôr do Sol | SOL NASCENTE E POR DO SOL | `53001080531` | **manual_reviewed** |
| `RA-XXXIII` | 33 | Arniqueira | ARNIQUEIRA | `53001080532` | normalized_exact |
| `RA-XXXIV` | 34 | Arapoanga | ARAPOANGA | `53001080545` | normalized_exact |
| `RA-XXXV` | 35 | Água Quente | AGUA QUENTE | `53001080546` | normalized_exact |

## 6. Cobertura por fonte

| Fonte | RAs cobertas | Ausentes |
|---|---|---|
| Malha oficial (IBRAM) | 35 | — |
| Subdistritos IBGE | 35 | — |
| População Censo 2022 | 33 | Arapoanga, Água Quente |
| População Censo 2010 | 19 | as 16 criadas depois |
| Balanço criminal SSP-DF | 33 | Arapoanga, Água Quente |
| Estabelecimentos CNES | 34 | Água Quente |
| Clima (Open-Meteo) | 35 | — |

Arapoanga e Água Quente, criadas em 2019, ainda não aparecem separadamente no
IBGE nem na SSP-DF — as duas fontes as contabilizam dentro das RAs de origem
(Planaltina e Recanto das Emas). A soma das 33 RAs publicadas pelo IBGE bate
exatamente com o total do DF no Censo 2022, o que confirma a interpretação.

## 7. Mudança de território entre os Censos

Das 35 RAs atuais, **19 existiam como subdistrito em 2010**. As outras 16 foram
desmembradas de RAs preexistentes.

Consequência verificada nos dados: **todas as 19 RAs de 2010 fazem fronteira
com pelo menos uma RA criada depois**, ou seja, nenhuma manteve o território
intacto. Por isso o projeto **não publica crescimento populacional por RA** —
ver [`data_quality.md` §2.10](./data_quality.md) e o modelo
[`int_region_lineage`](../dbt/models/intermediate/int_region_lineage.sql).

A RA de origem de cada RA nova é inferida pela fração do próprio contorno que
faz fronteira com uma RA preexistente, e só é afirmada quando passa de 50%.
Com esse limiar, apenas duas origens são afirmadas:

| RA criada depois | Origem inferida | Fração do contorno |
|---|---|---|
| Sol Nascente/Pôr do Sol | Ceilândia | 73,5% |
| Sudoeste/Octogonal | Plano Piloto | 58,7% |

Para as outras 14, a interface diz "na RA de origem" sem nomear — porque a
evidência geométrica não é suficiente para afirmar qual é.

## 8. Verificação automática

`dbt/tests/assert_region_keys_are_consistent.sql` falha o pipeline se:

* um subdistrito IBGE for usado por mais de uma RA;
* uma RA da malha do GDF não tiver mapeamento;
* o mapeamento apontar para uma RA que não existe na malha.

`ingestion/regions.py` registra um alerta em `meta.data_quality_check` se
qualquer das duas fontes deixar de retornar exatamente 35 registros — o DF cria
RAs por lei, e isso exige revisão humana do mapeamento, não ajuste automático.
