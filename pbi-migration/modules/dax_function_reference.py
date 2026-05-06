"""
DAX Function Reference — extracted from Microsoft official documentation.
Total functions: 382
Used by get_relevant_dax_docs() to dynamically inject only the functions
that appear in a given .pbix file into the LLM system prompt.
"""

DAX_FUNCTIONS = {
    "ABS": {
        "description": "Devuelve el valor absoluto de un número.",
        "syntax": "ABS(<number>)",
    },
    "ACCRINT": {
        "description": "Devuelve el interés acumulado de una seguridad que paga intereses periódicos.",
    },
    "ACCRINTM": {
        "description": "Devuelve el interés acumulado para una seguridad que paga intereses a vencimiento.",
        "syntax": "ACCRINTM(<issue>, <maturity>, <rate>, <par>[, <basis>])",
    },
    "ACOS": {
        "description": "Devuelve el arcocoseno, o coseno inverso, de un número.",
        "syntax": "ACOS(number)",
    },
    "ACOSH": {
        "description": "Devuelve el coseno hiperbólico inverso de un número.",
        "syntax": "ACOSH(number)",
    },
    "ACOT": {
        "description": "Devuelve la arccotangent, o la cotangente inversa, de un número.",
        "syntax": "ACOT(number)",
    },
    "ACOTH": {
        "description": "Devuelve la cotangente hiperbólica inversa de un número.",
        "syntax": "ACOTH(number)",
    },
    "ADDCOLUMNS": {
        "description": "Agrega columnas calculadas a la tabla o expresión de tabla especificadas.",
        "syntax": "ADDCOLUMNS(<table>, <name>, <expression>[, <name>, <expression>]…)",
    },
    "ADDMISSINGITEMS": {
        "description": "Agrega combinaciones de elementos de varias columnas a una tabla si aún no existen.",
        "syntax": "ADDMISSINGITEMS ( [<showAll_columnName> [, <showAll_columnName> [, … ] ] ], <table> [, <groupBy_columnName> [, [<filterTable>] [, <groupBy_columnName> [, [<filterTable>] [, … ] ] ] ] ] ] )",
    },
    "ALL": {
        "description": "Devuelve todas las filas de una tabla o todos los valores de una columna, omiiendo los filtros que se podrían haber aplicado.",
        "syntax": "ALL( [<table> | <column>[, <column>[, <column>[,…]]]] )",
    },
    "ALLCROSSFILTERED": {
        "description": "Borre todos los filtros que se aplican a una tabla.",
        "syntax": "ALLCROSSFILTERED(<table>)",
    },
    "ALLEXCEPT": {
        "description": "Quita todos los filtros de contexto de la tabla, excepto los filtros que se han aplicado a las columnas especificadas.",
        "syntax": "ALLEXCEPT(<table>,<column>[,<column>[,…]])",
    },
    "ALLNOBLANKROW": {
        "description": "En la tabla primaria de una relación, devuelve todas las filas, pero la fila en blanco, o todos los valores distintos de una columna, pero la fila en blanco, e ignora los filtros de contexto que puedan existir.",
        "syntax": "ALLNOBLANKROW( {<table> | <column>[, <column>[, <column>[,…]]]} )",
    },
    "ALLSELECTED": {
        "description": "Quita filtros de contexto de columnas y filas de la consulta actual, a la vez que conserva todos los demás filtros de contexto o filtros explícitos.",
        "syntax": "ALLSELECTED([<tableName> | <columnName>[, <columnName>[, <columnName>[,…]]]] )",
    },
    "AMORDEGRC": {
        "description": "Devuelve la amortización de cada período contable. De forma similar a AMORLINC, excepto que se aplica un coeficiente de amortización en función de la vida de los activos.",
        "syntax": "AMORDEGRC(<cost>, <date_purchased>, <first_period>, <salvage>, <period>, <rate>[, <basis>])",
    },
    "AMORLINC": {
        "description": "Devuelve la amortización de cada período contable.",
        "syntax": "AMORLINC(<cost>, <date_purchased>, <first_period>, <salvage>, <period>, <rate>[, <basis>])",
    },
    "AND": {
        "description": "Comprueba si ambos argumentos son TRUE y devuelve TRUE si ambos argumentos son TRUE .",
        "syntax": "AND(<logical1>,<logical2>)",
    },
    "APPROXIMATEDISTINCTCOUNT": {
        "description": "Devuelve un recuento estimado de valores únicos en una columna.",
        "syntax": "APPROXIMATEDISTINCTCOUNT(<columnName>)",
    },
    "ASIN": {
        "description": "Devuelve el arcoseno, o seno inverso, de un número.",
        "syntax": "ASIN(number)",
    },
    "ASINH": {
        "description": "Devuelve el seno hiperbólico inverso de un número.",
        "syntax": "ASINH(number)",
    },
    "ATAN": {
        "description": "Devuelve la arcotangente, o tangente inversa, de un número.",
        "syntax": "ATAN(number)",
    },
    "ATANH": {
        "description": "Devuelve la tangente hiperbólica inversa de un número.",
        "syntax": "ATANH(number)",
    },
    "AVERAGE": {
        "description": "Devuelve el promedio (media aritmética) de todos los números de una columna.",
        "syntax": "AVERAGE(<column>)",
    },
    "AVERAGEA": {
        "description": "Devuelve el promedio (media aritmética) de los valores de una columna.",
        "syntax": "AVERAGEA(<column>)",
    },
    "AVERAGEX": {
        "description": "Calcula el promedio (media aritmética) de un conjunto de expresiones evaluadas sobre una tabla.",
        "syntax": "AVERAGEX(<table>,<expression>)",
    },
    "BETA.DIST": {
        "description": "Devuelve la distribución beta.",
        "syntax": "BETA.DIST(x,alpha,beta,cumulative,[A],[B])",
    },
    "BETA.INV": {
        "description": "Devuelve el inverso de la función de densidad de probabilidad acumulativa beta (BETA.DIST).",
        "syntax": "BETA.INV(probability,alpha,beta,[A],[B])",
    },
    "BITAND": {
        "description": "Devuelve un \"ANDbit a bit \" de dos números.",
        "syntax": "BITAND(<number>, <number>)",
    },
    "BITLSHIFT": {
        "description": "Devuelve un número desplazado a la izquierda por el número especificado de bits.",
        "syntax": "BITLSHIFT(<Number>, <Shift_Amount>)",
    },
    "BITOR": {
        "description": "Devuelve un \"ORbit a bit \" de dos números.",
        "syntax": "BITOR(<number>, <number>)",
    },
    "BITRSHIFT": {
        "description": "Devuelve un número desplazado hacia la derecha por el número especificado de bits.",
        "syntax": "BITRSHIFT(<Number>, <Shift_Amount>)",
    },
    "BITXOR": {
        "description": "Devuelve un \"XOR\" bit a bit de dos números.",
        "syntax": "BITXOR(<number>, <number>)",
    },
    "BLANK": {
        "description": "Devuelve un valor en blanco.",
    },
    "CALCULATE": {
        "description": "Evalúa una expresión en un contexto de filtro modificado.",
        "syntax": "CALCULATE(<expression>[, <filter1> [, <filter2> [, …]]])",
    },
    "CALCULATETABLE": {
        "description": "Evalúa una expresión de tabla en un contexto de filtro modificado.",
        "syntax": "CALCULATETABLE(<expression>[, <filter1> [, <filter2> [, …]]])",
    },
    "CALENDAR": {
        "description": "Devuelve una tabla con una sola columna denominada \"Date\" que contiene un conjunto contiguo de fechas.",
        "syntax": "CALENDAR(<start_date>, <end_date>)",
    },
    "CALENDARAUTO": {
        "description": "Devuelve una tabla con una sola columna denominada \"Date\" que contiene un conjunto contiguo de fechas.",
        "syntax": "CALENDARAUTO([fiscal_year_end_month])",
    },
    "CEILING": {
        "description": "Redondea un número hacia arriba, hasta el entero más cercano o hasta el múltiplo más cercano de importancia.",
        "syntax": "CEILING(<number>, <significance>)",
    },
    "CHISQ.DIST": {
        "description": "Devuelve la distribución chi cuadrado.",
        "syntax": "CHISQ.DIST(<x>, <deg_freedom>, <cumulative>)",
    },
    "CHISQ.DIST.RT": {
        "description": "Devuelve la probabilidad de cola derecha de la distribución chi cuadrado.",
        "syntax": "CHISQ.DIST.RT(<x>, <deg_freedom>)",
    },
    "CHISQ.INV": {
        "description": "Devuelve el inverso de la probabilidad de cola izquierda de la distribución chi cuadrado.",
        "syntax": "CHISQ.INV(probability,deg_freedom)",
    },
    "CHISQ.INV.RT": {
        "description": "Devuelve el inverso de la probabilidad de cola derecha de la distribución chi cuadrado.",
        "syntax": "CHISQ.INV.RT(probability,deg_freedom)",
    },
    "CLOSINGBALANCEMONTH": {
        "description": "Evalúa la expresión en la última fecha del mes en el contexto actual.",
        "syntax": "CLOSINGBALANCEMONTH(<expression>, <dates> or <calendar>[,<filter>])",
    },
    "CLOSINGBALANCEQUARTER": {
        "description": "Evalúa la expresión en la última fecha del trimestre en el contexto actual.",
        "syntax": "CLOSINGBALANCEQUARTER(<expression>,<dates> or <calendar>[,<filter>])",
    },
    "CLOSINGBALANCEWEEK": {
        "description": "Evalúa la expresión en la última fecha de la semana en el contexto actual.",
    },
    "CLOSINGBALANCEYEAR": {
        "description": "Evalúa la expresión en la última fecha del año en el contexto actual.",
        "syntax": "CLOSINGBALANCEYEAR(<expression>,<dates> or <calendar>[,<filter>][, <year_end_date>])",
    },
    "COALESCE": {
        "description": "Devuelve la primera expresión que no se evalúa como BLANK.",
        "syntax": "COALESCE(<expression>, <expression>[, <expression>]…)",
    },
    "COLUMNSTATISTICS": {
        "description": "Devuelve una tabla de estadísticas con respecto a cada columna de cada tabla del modelo.",
    },
    "COMBIN": {
        "description": "Devuelve el número de combinaciones de un número determinado de elementos.",
        "syntax": "COMBIN(number, number_chosen)",
    },
    "COMBINA": {
        "description": "Devuelve el número de combinaciones (con repeticiones) para un número determinado de elementos.",
        "syntax": "COMBINA(number, number_chosen)",
    },
    "COMBINEVALUES": {
        "description": "Combina dos o más cadenas de texto en una cadena de texto.",
        "syntax": "COMBINEVALUES(<delimiter>, <expression>, <expression>[, <expression>]…)",
    },
    "CONCATENATE": {
        "description": "Combina dos cadenas de texto en una cadena de texto.",
        "syntax": "CONCATENATE(<text1>, <text2>)",
    },
    "CONCATENATEX": {
        "description": "Concatena el resultado de una expresión evaluada para cada fila de una tabla.",
        "syntax": "CONCATENATEX(<table>, <expression>[, <delimiter> [, <orderBy_expression> [, <order>]]...])",
    },
    "CONFIDENCE.NORM": {
        "description": "El intervalo de confianza es un intervalo de valores.",
        "syntax": "CONFIDENCE.NORM(alpha,standard_dev,size)",
    },
    "CONFIDENCE.T": {
        "description": "Devuelve el intervalo de confianza de una media de población, utilizando la distribución t de Student.",
        "syntax": "CONFIDENCE.T(alpha,standard_dev,size)",
    },
    "CONTAINS": {
        "description": "Devuelve true si existen valores para todas las columnas a las que se hace referencia o están contenidos en esas columnas; de lo contrario, la función devuelve false.",
        "syntax": "CONTAINS(<table>, <columnName>, <value>[, <columnName>, <value>]…)",
    },
    "CONTAINSROW": {
        "description": "Devuelve TRUE si existe o contiene una fila de valores en una tabla; de lo contrario, devuelve FALSE .",
        "syntax": "CONTAINSROW(<Table>, <Value> [, <Value> [, …] ] )",
    },
    "CONTAINSSTRING": {
        "description": "Devuelve TRUE o FALSE que indican si una cadena contiene otra cadena.",
        "syntax": "CONTAINSSTRING(<within_text>, <find_text>)",
    },
    "CONTAINSSTRINGEXACT": {
        "description": "Devuelve TRUE o FALSE que indican si una cadena contiene otra cadena.",
        "syntax": "CONTAINSSTRINGEXACT(<within_text>, <find_text>)",
    },
    "CONVERT": {
        "description": "Convierte una expresión de un tipo de datos en otro.",
        "syntax": "CONVERT(<Expression>, <Datatype>)",
    },
    "COS": {
        "description": "Devuelve el coseno del ángulo especificado.",
        "syntax": "COS(number)",
    },
    "COSH": {
        "description": "Devuelve el coseno hiperbólico de un número.",
        "syntax": "COSH(number)",
    },
    "COT": {
        "description": "Devuelve la cotangente de un ángulo especificado en radianes.",
        "syntax": "COT (<number>)",
    },
    "COTH": {
        "description": "Devuelve la cotangente hiperbólica de un ángulo hiperbólico.",
        "syntax": "COTH (<number>)",
    },
    "COUNT": {
        "description": "Cuenta el número de filas de la columna especificada que contienen valores que no están en blanco. No admite valores booleanos.",
        "syntax": "COUNT(<column>)",
    },
    "COUNTA": {
        "description": "Cuenta el número de filas de la columna especificada que contienen valores que no están en blanco. Admite valores booleanos.",
        "syntax": "COUNTA(<column>)",
    },
    "COUNTAX": {
        "description": "Cuenta los resultados que no están en blanco al evaluar el resultado de una expresión sobre una tabla.",
        "syntax": "COUNTAX(<table>,<expression>)",
    },
    "COUNTBLANK": {
        "description": "Cuenta el número de celdas en blanco de una columna.",
        "syntax": "COUNTBLANK(<column>)",
    },
    "COUNTROWS": {
        "description": "Cuenta el número de filas de la tabla especificada o en una tabla definida por una expresión.",
        "syntax": "COUNTROWS([<table>])",
    },
    "COUNTX": {
        "description": "Cuenta el número de filas que contienen un número o una expresión que se evalúa como un número, al evaluar una expresión sobre una tabla.",
        "syntax": "COUNTX(<table>,<expression>)",
    },
    "COUPDAYBS": {
        "description": "Devuelve el número de días desde el principio de un período de cupón hasta su fecha de liquidación.",
        "syntax": "COUPDAYBS(<settlement>, <maturity>, <frequency>[, <basis>])",
    },
    "COUPDAYS": {
        "description": "Devuelve el número de días del período de cupón que contiene la fecha de liquidación.",
        "syntax": "COUPDAYS(<settlement>, <maturity>, <frequency>[, <basis>])",
    },
    "COUPDAYSNC": {
        "description": "Devuelve el número de días desde la fecha de liquidación hasta la siguiente fecha del cupón.",
        "syntax": "COUPDAYSNC(<settlement>, <maturity>, <frequency>[, <basis>])",
    },
    "COUPNCD": {
        "description": "Devuelve la siguiente fecha del cupón después de la fecha de liquidación.",
        "syntax": "COUPNCD(<settlement>, <maturity>, <frequency>[, <basis>])",
    },
    "COUPNUM": {
        "description": "Devuelve el número de cupones pagaderos entre la fecha de liquidación y la fecha de vencimiento, redondeada hasta el cupón entero más cercano.",
        "syntax": "COUPNUM(<settlement>, <maturity>, <frequency>[, <basis>])",
    },
    "COUPPCD": {
        "description": "Devuelve la fecha del cupón anterior antes de la fecha de liquidación.",
        "syntax": "COUPPCD(<settlement>, <maturity>, <frequency>[, <basis>])",
    },
    "CROSSFILTER": {
        "description": "Especifica la dirección de filtrado cruzado que se va a usar en un cálculo de una relación que existe entre dos columnas.",
        "syntax": "CROSSFILTER(<columnName1>, <columnName2>, <direction>)",
    },
    "CROSSJOIN": {
        "description": "Devuelve una tabla que contiene el producto cartesiano de todas las filas de todas las tablas de los argumentos.",
        "syntax": "CROSSJOIN(<table>, <table>[, <table>]…)",
    },
    "CUMIPMT": {
        "description": "Devuelve el interés acumulado pagado en un préstamo entre start_period y end_period.",
        "syntax": "CUMIPMT(<rate>, <nper>, <pv>, <start_period>, <end_period>, <type>)",
    },
    "CUMPRINC": {
        "description": "Devuelve la entidad de seguridad acumulativa pagada en un préstamo entre start_period y end_period.",
        "syntax": "CUMPRINC(<rate>, <nper>, <pv>, <start_period>, <end_period>, <type>)",
    },
    "CURRENCY": {
        "description": "Evalúa el argumento y devuelve el resultado como tipo de datos currency.",
        "syntax": "CURRENCY(<value>)",
    },
    "CURRENTGROUP": {
        "description": "Devuelve un conjunto de filas del argumento table de una expresión GROUPBY.",
        "syntax": "CURRENTGROUP ( )",
    },
    "CUSTOMDATA": {
        "description": "Devuelve el contenido de la propiedad CustomData en la cadena de conexión.",
    },
    "DATATABLE": {
        "description": "Proporciona un mecanismo para declarar un conjunto insertado de valores de datos.",
        "syntax": "DATATABLE (ColumnName1, DataType1, ColumnName2, DataType2..., {{Value1, Value2...}, {ValueN, ValueN+1...}...})",
    },
    "DATE": {
        "description": "Devuelve la fecha especificada en formato datetime.",
        "syntax": "DATE(<year>, <month>, <day>)",
    },
    "DATEADD": {
        "description": "Devuelve una tabla que contiene una columna de fechas, desplazada hacia delante o hacia atrás en el tiempo por el número especificado de intervalos de las fechas en el contexto actual.",
        "syntax": "DATEADD(<dates> or <calendar>, <number_of_intervals>, <interval>[,<Extension>],[, <Truncation>])",
    },
    "DATEDIFF": {
        "description": "Devuelve el número de límites de intervalo entre dos fechas.",
        "syntax": "DATEDIFF(<Date1>, <Date2>, <Interval>)",
    },
    "DATESBETWEEN": {
        "description": "Devuelve una tabla que contiene una columna de fechas que comienza con una fecha de inicio especificada y continúa hasta una fecha de finalización especificada.",
        "syntax": "DATESBETWEEN(<dates> or <calendar>, <StartDate>, <EndDate>)",
    },
    "DATESINPERIOD": {
        "description": "Devuelve una tabla que contiene una columna de fechas que comienza con una fecha de inicio especificada y continúa para el número especificado y el tipo de intervalos de fecha.",
    },
    "DATESMTD": {
        "description": "Devuelve una tabla que contiene una columna de las fechas del mes a la fecha, en el contexto actual.",
        "syntax": "DATESMTD(<dates> or <calendar>)",
    },
    "DATESQTD": {
        "description": "Devuelve una tabla que contiene una columna de las fechas del trimestre hasta la fecha, en el contexto actual.",
        "syntax": "DATESQTD(<dates> or <calendar>)",
    },
    "DATESWTD": {
        "description": "Devuelve una tabla que contiene una columna de las fechas de la semana a la fecha, en el contexto actual.",
    },
    "DATESYTD": {
        "description": "Devuelve una tabla que contiene una columna de las fechas del año hasta la fecha, en el contexto actual.",
        "syntax": "DATESYTD(<dates> or <calendar> [,<year_end_date>])",
    },
    "DATEVALUE": {
        "description": "Convierte una fecha en forma de texto en una fecha en formato datetime.",
        "syntax": "DATEVALUE(date_text)",
    },
    "DAY": {
        "description": "Devuelve el día del mes, un número comprendido entre 1 y 31.",
        "syntax": "DAY(<date>)",
    },
    "DB": {
        "description": "Devuelve la depreciación de un activo durante un período especificado",
        "syntax": "DB(<cost>, <salvage>, <life>, <period>[, <month>])",
    },
    "DDB": {
        "description": "Devuelve la depreciación de un activo durante un período especificado utilizando el método de doble disminución del saldo o algún otro método especificado.",
        "syntax": "DDB(<cost>, <salvage>, <life>, <period>[, <factor>])",
    },
    "DEGREES": {
        "description": "Convierte radianes en grados.",
        "syntax": "DEGREES(angle)",
    },
    "DETAILROWS": {
        "description": "Evalúa una expresión de filas de detalle definida para una medida y devuelve los datos.",
        "syntax": "DETAILROWS([Measure])",
    },
    "DISC": {
        "description": "Devuelve la tasa de descuento de una seguridad.",
        "syntax": "DISC(<settlement>, <maturity>, <pr>, <redemption>[, <basis>])",
    },
    "DISTINCTCOUNT": {
        "description": "Cuenta el número de valores distintos de una columna.",
        "syntax": "DISTINCTCOUNT(<column>)",
    },
    "DISTINCTCOUNTNOBLANK": {
        "description": "Cuenta el número de valores distintos de una columna.",
        "syntax": "DISTINCTCOUNTNOBLANK(<column>)",
    },
    "DIVIDE": {
        "description": "Realiza la división y devuelve un resultado alternativo o BLANK() en la división en 0.",
        "syntax": "DIVIDE(<numerator>, <denominator> [,<alternateresult>])",
    },
    "DOLLARDE": {
        "description": "Convierte un precio en dólares expresado como una parte entera y una parte de fracción, como 1,02, en un precio en dólares expresado como un número decimal.",
        "syntax": "DOLLARDE(<fractional_dollar>, <fraction>)",
    },
    "DOLLARFR": {
        "description": "Convierte un precio en dólares expresado como una parte entera y una parte de fracción, como 1,02, en un precio en dólares expresado como un número decimal.",
        "syntax": "DOLLARFR(<decimal_dollar>, <fraction>)",
    },
    "DURATION": {
        "description": "Devuelve la duración de Macaoley para un valor de par asumido de $100.",
        "syntax": "DURATION(<settlement>, <maturity>, <coupon>, <yld>, <frequency>[, <basis>])",
    },
    "EARLIER": {
        "description": "Devuelve el valor actual de la columna especificada en un pase de evaluación externa de la columna mencionada.",
        "syntax": "EARLIER(<column>, <number>)",
    },
    "EARLIEST": {
        "description": "Devuelve el valor actual de la columna especificada en un pase de evaluación externa de la columna especificada.",
        "syntax": "EARLIEST(<column>)",
    },
    "EDATE": {
        "description": "Devuelve la fecha que es el número indicado de meses antes o después de la fecha de inicio.",
        "syntax": "EDATE(<start_date>, <months>)",
    },
    "EFFECT": {
        "description": "Devuelve la tasa de interés anual efectiva, dada la tasa de interés anual nominal y el número de períodos compuestos por año.",
        "syntax": "EFFECT(<nominal_rate>, <npery>)",
    },
    "ENDOFMONTH": {
        "description": "Devuelve la última fecha del mes en el contexto actual de la columna de fechas especificada.",
        "syntax": "ENDOFMONTH(<dates> or <calendar>)",
    },
    "ENDOFQUARTER": {
        "description": "Devuelve la última fecha del trimestre en el contexto actual de la columna de fechas especificada.",
        "syntax": "ENDOFQUARTER(<dates> or <calendar>)",
    },
    "ENDOFWEEK": {
        "description": "Devuelve la última fecha de la semana en el contexto actual de la columna de fechas especificada.",
    },
    "ENDOFYEAR": {
        "description": "Devuelve la última fecha del año en el contexto actual de la columna de fechas especificada.",
        "syntax": "ENDOFYEAR(<dates> or <calendar> [,<year_end_date>])",
    },
    "EOMONTH": {
        "description": "Devuelve la fecha en formato datetime del último día del mes, antes o después de un número especificado de meses.",
        "syntax": "EOMONTH(<start_date>, <months>)",
    },
    "ERROR": {
        "description": "Genera un error con un mensaje de error.",
        "syntax": "ERROR(<text>)",
    },
    "EVALUATEANDLOG": {
        "description": "Devuelve el valor del primer argumento y lo registra en un evento de generador de perfiles de registro de evaluación de DAX.",
        "syntax": "EVALUATEANDLOG(<Value>, [Label], [MaxRows])",
    },
    "EVEN": {
        "description": "Devuelve el número redondeado al entero par más cercano.",
        "syntax": "EVEN(number)",
    },
    "EXACT": {
        "description": "Compara dos cadenas de texto y devuelve TRUE si son exactamente iguales, FALSE de lo contrario.",
        "syntax": "EXACT(<text1>,<text2>)",
    },
    "EXCEPT": {
        "description": "Devuelve las filas de una tabla que no aparecen en otra tabla.",
        "syntax": "EXCEPT(<table_expression1>, <table_expression2>)",
    },
    "EXP": {
        "description": "Devuelve e elevado a la potencia de un número determinado.",
        "syntax": "EXP(<number>)",
    },
    "EXPON.DIST": {
        "description": "Devuelve la distribución exponencial.",
        "syntax": "EXPON.DIST(x,lambda,cumulative)",
    },
    "EXTERNALMEASURE": {
        "description": "Invoca una medida definida en un modelo remoto y devuelve su resultado.",
    },
    "FACT": {
        "description": "Devuelve el factorial de un número, igual a la serie 1*2*3*...* , que termina en el número especificado.",
        "syntax": "FACT(<number>)",
    },
    "FALSE": {
        "description": "Devuelve el valor lógico FALSE .",
    },
    "FILTER": {
        "description": "Devuelve una tabla que representa un subconjunto de otra tabla o expresión.",
        "syntax": "FILTER(<table>,<filter>)",
    },
    "FILTERS": {
        "description": "Devuelve una tabla de valores que se aplica directamente como filtros a columnName .",
        "syntax": "FILTERS(<columnName>)",
    },
    "FIND": {
        "description": "Devuelve la posición inicial de una cadena de texto dentro de otra cadena de texto.",
        "syntax": "FIND(<find_text>, <within_text>[, [<start_num>][, <NotFoundValue>]])",
    },
    "FIRST": {
        "description": "Solo se usa en cálculos visuales. Recupera un valor de la matriz visual de la primera fila de un eje.",
    },
    "FIRSTDATE": {
        "description": "Devuelve la primera fecha del contexto actual de la columna de fechas especificada.",
        "syntax": "FIRSTDATE(<dates> or <calendar>)",
    },
    "FIXED": {
        "description": "Redondea un número al número especificado de decimales y devuelve el resultado como texto.",
        "syntax": "FIXED(<number>, <decimals>, <no_commas>)",
    },
    "FLOOR": {
        "description": "Redondea un número hacia abajo, hacia cero, hasta el múltiplo más cercano de importancia.",
        "syntax": "FLOOR(<number>, <significance>)",
    },
    "FORMAT": {
        "description": "Convierte un valor en texto según el formato especificado.",
        "syntax": "FORMAT(<value>, <format_string>[, <locale_name>])",
    },
    "FV": {
        "description": "Calcula el valor futuro de una inversión basándose en una tasa de interés constante.",
        "syntax": "FV(<rate>, <nper>, <pmt>[, <pv>[, <type>]])",
    },
    "GCD": {
        "description": "Devuelve el mayor divisor común de dos o más enteros.",
        "syntax": "GCD(number1, number2)",
    },
    "GENERATE": {
        "description": "Devuelve una tabla con el producto cartesiano entre cada fila de tabla1 y la tabla que resulta de evaluar tabla2 en el contexto de la fila actual de tabla1.",
        "syntax": "GENERATE(<table1>, <table2>)",
    },
    "GENERATEALL": {
        "description": "Devuelve una tabla con el producto cartesiano entre cada fila de tabla1 y la tabla que resulta de evaluar tabla2 en el contexto de la fila actual de tabla1.",
        "syntax": "GENERATEALL(<table1>, <table2>)",
    },
    "GENERATESERIES": {
        "description": "Devuelve una sola tabla de columnas que contiene los valores de una serie aritmética.",
        "syntax": "GENERATESERIES(<startValue>, <endValue>[, <incrementValue>])",
    },
    "GEOMEAN": {
        "description": "Devuelve la media geométrica de los números de una columna.",
        "syntax": "GEOMEAN(<column>)",
    },
    "GEOMEANX": {
        "description": "Devuelve la media geométrica de una expresión evaluada para cada fila de una tabla.",
        "syntax": "GEOMEANX(<table>, <expression>)",
    },
    "GROUPBY": {
        "description": "De forma similar a la función SUMMARIZE, GROUPBY no realiza una CALCULATE implícita para las columnas de extensión que agrega.",
        "syntax": "GROUPBY (<table> [, <groupBy_columnName> [, <groupBy_columnName> [, …]]] [, <name>, <expression> [, <name>, <expression> [, …]]])",
    },
    "HASONEFILTER": {
        "description": "Devuelve TRUE cuando el número de valores filtrados directamente en columnName es uno; De lo contrario, devuelve FALSE .",
        "syntax": "HASONEFILTER(<columnName>)",
    },
    "HASONEVALUE": {
        "description": "Devuelve TRUE cuando el contexto de columnName se ha filtrado solo a un valor distinto. De lo contrario, es FALSE .",
        "syntax": "HASONEVALUE(<columnName>)",
    },
    "HOUR": {
        "description": "Devuelve la hora como un número de 0 (12:00 A.M.) a 23 (11:00 P.M.).",
        "syntax": "HOUR(<datetime>)",
    },
    "IF": {
        "description": "Comprueba una condición y devuelve un valor cuando TRUE ; de lo contrario, devuelve un segundo valor.",
        "syntax": "IF(<logical_test>, <value_if_true>[, <value_if_false>])",
    },
    "IF.EAGER": {
        "description": "Comprueba una condición y devuelve un valor cuando TRUE ; de lo contrario, devuelve un segundo valor. Usa un plan de ejecución diligente que siempre ejecuta las expresiones de rama independientemente de la expresión de condición.",
        "syntax": "IF.EAGER(<logical_test>, <value_if_true>[, <value_if_false>])",
    },
    "IFERROR": {
        "description": "Evalúa una expresión y devuelve un valor especificado si la expresión devuelve un error.",
        "syntax": "IFERROR(value, value_if_error)",
    },
    "IGNORE": {
        "description": "Modifica SUMMARIZECOLUMNS omitiendo expresiones específicas de la evaluación de BLANK/NULL.",
        "syntax": "IGNORE(<expression>)",
    },
    "INDEX": {
        "description": "Devuelve una fila en una posición absoluta, especificada por el parámetro position, dentro de la partición especificada, ordenada por el orden especificado o en el eje especificado.",
    },
    "INT": {
        "description": "Redondea un número hasta el entero más cercano.",
        "syntax": "INT(<number>)",
    },
    "INTERSECT": {
        "description": "Devuelve la intersección de fila de dos tablas, conservando duplicados.",
        "syntax": "INTERSECT(<table_expression1>, <table_expression2>)",
    },
    "INTRATE": {
        "description": "Devuelve la tasa de interés de una seguridad totalmente invertida.",
        "syntax": "INTRATE(<settlement>, <maturity>, <investment>, <redemption>[, <basis>])",
    },
    "IPMT": {
        "description": "Devuelve el pago de intereses durante un período determinado para una inversión basada en pagos periódicos, constantes y un tipo de interés constante.",
        "syntax": "IPMT(<rate>, <per>, <nper>, <pv>[, <fv>[, <type>]])",
    },
    "ISAFTER": {
        "description": "Una función booleana que emula el comportamiento de una cláusula Start At y devuelve true para una fila que cumple todos los parámetros de condición.",
        "syntax": "ISAFTER(<scalar_expression>, <scalar_expression>[, sort_order [, <scalar_expression>, <scalar_expression>[, sort_order]]…)",
    },
    "ISBLANK": {
        "description": "Comprueba si un valor está en blanco y devuelve TRUE o FALSE .",
        "syntax": "ISBLANK(<value>)",
    },
    "ISBOOLEAN": {
        "description": "Comprueba si un valor es un valor lógico, ( TRUE o FALSE ), y devuelve TRUE o FALSE . Alias de ISLOGICAL.",
    },
    "ISCROSSFILTERED": {
        "description": "Devuelve TRUE cuando se filtra columnName u otra columna de la misma tabla o relacionada.",
        "syntax": "ISCROSSFILTERED(<TableNameOrColumnName>)",
    },
    "ISCURRENCY": {
        "description": "Comprueba si un valor es un número decimal y devuelve TRUE o FALSE . Alias de ISDECIMAL.",
    },
    "ISDATETIME": {
        "description": "Comprueba si un valor es una fecha y hora y devuelve TRUE o FALSE .",
    },
    "ISDECIMAL": {
        "description": "Comprueba si un valor es un número decimal y devuelve TRUE o FALSE . Alias de ISCURRENCY.",
    },
    "ISDOUBLE": {
        "description": "Comprueba si un valor es un número de punto flotante y devuelve TRUE o FALSE .",
    },
    "ISEMPTY": {
        "description": "Comprueba si una tabla está vacía.",
        "syntax": "ISEMPTY(<table_expression>)",
    },
    "ISERROR": {
        "description": "Comprueba si un valor es un error y devuelve TRUE o FALSE .",
        "syntax": "ISERROR(<value>)",
    },
    "ISEVEN": {
        "description": "Devuelve TRUE si el número es par o FALSE si el número es impar.",
        "syntax": "ISEVEN(number)",
    },
    "ISFILTERED": {
        "description": "Devuelve TRUE cuando se filtra directamente columnName .",
        "syntax": "ISFILTERED(<TableNameOrColumnName>)",
    },
    "ISINSCOPE": {
        "description": "Devuelve true cuando la columna especificada es el nivel de una jerarquía de niveles.",
        "syntax": "ISINSCOPE(<columnName>)",
    },
    "ISINT64": {
        "description": "Comprueba si un valor es un número entero y devuelve TRUE o FALSE . Alias de ISINTEGER.",
    },
    "ISINTEGER": {
        "description": "Comprueba si un valor es un número entero y devuelve TRUE o FALSE . Alias de ISINT64.",
    },
    "ISLOGICAL": {
        "description": "Comprueba si un valor es un valor lógico, ( TRUE o FALSE ), y devuelve TRUE o FALSE . Alias de ISBOOLEAN.",
        "syntax": "ISLOGICAL(<value>)",
    },
    "ISNONTEXT": {
        "description": "Comprueba si un valor no es texto (las celdas en blanco no son texto) y devuelve TRUE o FALSE .",
        "syntax": "ISNONTEXT(<value>)",
    },
    "ISNUMBER": {
        "description": "Comprueba si un valor es un número y devuelve TRUE o FALSE . Alias de ISNUMERIC.",
        "syntax": "ISNUMBER(<value>)",
    },
    "ISNUMERIC": {
        "description": "Comprueba si un valor es un número y devuelve TRUE o FALSE . Alias de ISNUMBER.",
    },
    "ISO.CEILING": {
        "description": "Redondea un número hacia arriba, hasta el entero más cercano o hasta el múltiplo más cercano de importancia.",
        "syntax": "ISO.CEILING(<number>[, <significance>])",
    },
    "ISODD": {
        "description": "Devuelve TRUE si el número es impar o FALSE si el número es par.",
        "syntax": "ISODD(number)",
    },
    "ISONORAFTER": {
        "description": "Una función booleana que emula el comportamiento de una cláusula Start At y devuelve true para una fila que cumple todos los parámetros de condición.",
        "syntax": "ISONORAFTER(<scalar_expression>, <scalar_expression>[, sort_order [, <scalar_expression>, <scalar_expression>[, sort_order]]…)",
    },
    "ISPMT": {
        "description": "Calcula el interés pagado (o recibido) durante el período especificado de un préstamo (o inversión) con pagos de capital par.",
        "syntax": "ISPMT(<rate>, <per>, <nper>, <pv>)",
    },
    "ISSELECTEDMEASURE": {
        "description": "Usada por expresiones para los elementos de cálculo para determinar la medida que se encuentra en contexto es una de las especificadas en una lista de medidas.",
        "syntax": "ISSELECTEDMEASURE( M1, M2, ... )",
    },
    "ISSTRING": {
        "description": "Comprueba si un valor es texto y devuelve TRUE o FALSE . Alias de ISTEXT.",
    },
    "ISSUBTOTAL": {
        "description": "Crea otra columna en una expresión de SUMMARIZE que devuelve True si la fila contiene valores subtotales para la columna especificada como argumento; de lo contrario, devuelve False.",
        "syntax": "ISSUBTOTAL(<columnName>)",
    },
    "ISTEXT": {
        "description": "Comprueba si un valor es texto y devuelve TRUE o FALSE . Alias de ISSTRING.",
        "syntax": "ISTEXT(<value>)",
    },
    "KEEPFILTERS": {
        "description": "Modifica cómo se aplican los filtros al evaluar una función CALCULATE o CALCULATETABLE.",
        "syntax": "KEEPFILTERS(<expression>)",
    },
    "LAST": {
        "description": "Solo se usa en cálculos visuales. Recupera un valor de la matriz visual de la última fila de un eje.",
    },
    "LASTDATE": {
        "description": "Devuelve la última fecha del contexto actual de la columna de fechas especificada.",
        "syntax": "LASTDATE(<dates> or <calendar>)",
    },
    "LCM": {
        "description": "Devuelve el múltiplo menos común de enteros.",
        "syntax": "LCM(number1, number2)",
    },
    "LEFT": {
        "description": "Devuelve el número especificado de caracteres desde el inicio de una cadena de texto.",
        "syntax": "LEFT(<text>, <num_chars>)",
    },
    "LEN": {
        "description": "Devuelve el número de caracteres de una cadena de texto.",
        "syntax": "LEN(<text>)",
    },
    "LINEST": {
        "description": "Usa el método Least Squares para calcular una línea recta que mejor se adapte a los datos especificados.",
        "syntax": "LINEST ( <columnY>, <columnX>[, …][, <const>] )",
    },
    "LINESTX": {
        "description": "Usa el método Least Squares para calcular una línea recta que mejor se adapte a los datos especificados. Resultado de los datos de las expresiones evaluadas para cada fila de una tabla.",
        "syntax": "LINESTX ( <table>, <expressionY>, <expressionX>[, …][, <const>] )",
    },
    "LN": {
        "description": "Devuelve el logaritmo natural de un número.",
        "syntax": "LN(<number>)",
    },
    "LOG": {
        "description": "Devuelve el logaritmo de un número a la base que especifique.",
        "syntax": "LOG(<number>,<base>)",
    },
    "LOG10": {
        "description": "Devuelve el logaritmo base-10 de un número.",
        "syntax": "LOG10(<number>)",
    },
    "LOOKUPVALUE": {
        "description": "Devuelve el valor de la fila que cumple todos los criterios especificados por las condiciones de búsqueda. La función puede aplicar una o varias condiciones de búsqueda.",
    },
    "LOOKUPWITHTOTALS": {
        "description": "Solo en el modo de cálculo visual. Busque el valor cuando se apliquen filtros. Los filtros no especificados no se deducirán.",
        "syntax": "LOOKUPWITHTOTALS(<expression>, <colref>, <expression>[, <colref>, <expression>]...)",
    },
    "LOWER": {
        "description": "Convierte todas las letras de una cadena de texto en minúsculas.",
        "syntax": "LOWER(<text>)",
    },
    "MATCHBY": {
        "description": "En las funciones de ventana, define las columnas que se usan para determinar cómo hacer coincidir los datos e identificar el fila actual.",
        "syntax": "MATCHBY ( [<matchBy_columnName>[, matchBy_columnName [, …]]] )",
    },
    "MAX": {
        "description": "Devuelve el valor numérico más grande de una columna o entre dos expresiones escalares.",
        "syntax": "MAX(<column>)",
    },
    "MAXA": {
        "description": "Devuelve el valor más grande de una columna.",
        "syntax": "MAXA(<column>)",
    },
    "MAXX": {
        "description": "Evalúa una expresión para cada fila de una tabla y devuelve el valor numérico más grande.",
        "syntax": "MAXX(<table>,<expression>,[<variant>])",
    },
    "MDURATION": {
        "description": "Devuelve la duración modificada de Macaoley para una seguridad con un valor de par asumido de $100.",
        "syntax": "MDURATION(<settlement>, <maturity>, <coupon>, <yld>, <frequency>[, <basis>])",
    },
    "MEDIAN": {
        "description": "Devuelve la mediana de números de una columna.",
        "syntax": "MEDIAN(<column>)",
    },
    "MEDIANX": {
        "description": "Devuelve el número medio de una expresión evaluada para cada fila de una tabla.",
        "syntax": "MEDIANX(<table>, <expression>)",
    },
    "MID": {
        "description": "Devuelve una cadena de caracteres del centro de una cadena de texto, dada una posición inicial y una longitud.",
        "syntax": "MID(<text>, <start_num>, <num_chars>)",
    },
    "MIN": {
        "description": "Devuelve el valor numérico más pequeño de una columna o entre dos expresiones escalares.",
        "syntax": "MIN(<column>)",
    },
    "MINA": {
        "description": "Devuelve el valor más pequeño de una columna, incluidos los valores lógicos y los números representados como texto.",
        "syntax": "MINA(<column>)",
    },
    "MINUTE": {
        "description": "Devuelve el minuto como un número comprendido entre 0 y 59, dado un valor de fecha y hora.",
        "syntax": "MINUTE(<datetime>)",
    },
    "MINX": {
        "description": "Devuelve el valor numérico más pequeño que resulta de evaluar una expresión para cada fila de una tabla.",
        "syntax": "MINX(<table>, < expression>,[<variant>])",
    },
    "MOD": {
        "description": "Devuelve el resto después de dividir un número por un divisor. El resultado siempre tiene el mismo signo que el divisor.",
        "syntax": "MOD(<number>, <divisor>)",
    },
    "MONTH": {
        "description": "Devuelve el mes como un número del 1 (enero) al 12 (diciembre).",
        "syntax": "MONTH(<datetime>)",
    },
    "MOVINGAVERAGE": {
        "description": "Devuelve un promedio móvil calculado a lo largo del eje especificado de la matriz visual.",
    },
    "MROUND": {
        "description": "Devuelve un número redondeado al múltiplo deseado.",
        "syntax": "MROUND(<number>, <multiple>)",
    },
    "NAMEOF": {
        "description": "Devuelve el nombre de una tabla, columna, medida o calendario como una cadena de texto.",
    },
    "NATURALINNERJOIN": {
        "description": "Realiza una combinación interna de una tabla con otra tabla.",
        "syntax": "NATURALINNERJOIN(<LeftTable>, <RightTable>)",
    },
    "NATURALLEFTOUTERJOIN": {
        "description": "Realiza una combinación de LeftTable con RightTable.",
        "syntax": "NATURALLEFTOUTERJOIN(<LeftTable>, <RightTable>)",
    },
    "NETWORKDAYS": {
        "description": "Devuelve el número de días laborables completos entre dos fechas.",
        "syntax": "NETWORKDAYS(<start_date>, <end_date>[, <weekend>, <holidays>])",
    },
    "NEXT": {
        "description": "Solo se usa en cálculos visuales. Recupera un valor en la siguiente fila de un eje de la matriz visual.",
    },
    "NEXTDAY": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas del día siguiente, en función de la primera fecha especificada en la columna dates del contexto actual.",
        "syntax": "NEXTDAY(<dates> or <calendar>)",
    },
    "NEXTMONTH": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas del mes siguiente, en función de la primera fecha de la columna dates del contexto actual.",
        "syntax": "NEXTMONTH(<dates> or <calendar>)",
    },
    "NEXTQUARTER": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas del trimestre siguiente, en función de la primera fecha especificada en la columna dates, en el contexto actual.",
        "syntax": "NEXTQUARTER(<dates> or <calendar>)",
    },
    "NEXTWEEK": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas de la semana siguiente, en función de la primera fecha de la columna dates del contexto actual.",
    },
    "NEXTYEAR": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas del próximo año, en función de la primera fecha de la columna dates, en el contexto actual.",
        "syntax": "NEXTYEAR(<dates> or <calendar>[,<year_end_date>])",
    },
    "NOMINAL": {
        "description": "Devuelve la tasa de interés anual nominal, dada la tasa efectiva y el número de períodos compuestos por año.",
        "syntax": "NOMINAL(<effect_rate>, <npery>)",
    },
    "NONVISUAL": {
        "description": "Marca un filtro de valor en una expresión de SUMMARIZECOLUMNS como no visual.",
        "syntax": "NONVISUAL(<expression>)",
    },
    "NORM.DIST": {
        "description": "Devuelve la distribución normal para la media y la desviación estándar especificadas.",
        "syntax": "NORM.DIST(X, Mean, Standard_dev, Cumulative)",
    },
    "NORM.INV": {
        "description": "Inversa de la distribución acumulativa normal para la media y la desviación estándar especificadas.",
        "syntax": "NORM.INV(Probability, Mean, Standard_dev)",
    },
    "NORM.S.DIST": {
        "description": "Devuelve la distribución normal estándar (tiene una media de cero y una desviación estándar de uno).",
        "syntax": "NORM.S.DIST(Z, Cumulative)",
    },
    "NORM.S.INV": {
        "description": "Devuelve el inverso de la distribución acumulativa normal estándar.",
        "syntax": "NORM.S.INV(Probability)",
    },
    "NOT": {
        "description": "Cambia FALSE a TRUE o TRUE a FALSE .",
        "syntax": "NOT(<logical>)",
    },
    "NOW": {
        "description": "Devuelve la fecha y hora actuales en formato datetime.",
    },
    "NPER": {
        "description": "Devuelve el número de períodos de una inversión basada en pagos periódicos, constantes y un tipo de interés constante.",
        "syntax": "NPER(<rate>, <pmt>, <pv>[, <fv>[, <type>]])",
    },
    "ODD": {
        "description": "Devuelve el número redondeado al entero impar más cercano.",
        "syntax": "ODD(number)",
    },
    "ODDFPRICE": {
        "description": "Devuelve el precio por valor nominal de $100 de una seguridad que tiene un primer período impar (corto o largo).",
        "syntax": "ODDFPRICE(<settlement>, <maturity>, <issue>, <first_coupon>, <rate>, <yld>, <redemption>, <frequency>[, <basis>])",
    },
    "ODDFYIELD": {
        "description": "Devuelve el rendimiento de una seguridad que tiene un primer período impar (corto o largo).",
        "syntax": "ODDFYIELD(<settlement>, <maturity>, <issue>, <first_coupon>, <rate>, <pr>, <redemption>, <frequency>[, <basis>])",
    },
    "ODDLPRICE": {
        "description": "Devuelve el precio por valor nominal de $100 de una seguridad que tiene un período de último cupón impar (corto o largo).",
        "syntax": "ODDLPRICE(<settlement>, <maturity>, <last_interest>, <rate>, <yld>, <redemption>, <frequency>[, <basis>])",
    },
    "ODDLYIELD": {
        "description": "Devuelve el rendimiento de una seguridad que tiene un último período impar (corto o largo).",
        "syntax": "ODDLYIELD(<settlement>, <maturity>, <last_interest>, <rate>, <pr>, <redemption>, <frequency>[, <basis>])",
    },
    "OFFSET": {
        "description": "Devuelve una sola fila que se coloca antes o después de la fila actual dentro de la misma tabla, mediante un desplazamiento determinado.",
    },
    "OPENINGBALANCEMONTH": {
        "description": "Evalúa la expresión en la primera fecha del mes en el contexto actual.",
        "syntax": "OPENINGBALANCEMONTH(<expression>,<dates> or <calendar>[,<filter>])",
    },
    "OPENINGBALANCEQUARTER": {
        "description": "Evalúa la expresión en la primera fecha del trimestre, en el contexto actual.",
        "syntax": "OPENINGBALANCEQUARTER(<expression>,<dates> or <calendar>[,<filter>])",
    },
    "OPENINGBALANCEWEEK": {
        "description": "Evalúa la expresión en la primera fecha de la semana en el contexto actual.",
    },
    "OPENINGBALANCEYEAR": {
        "description": "Evalúa la expresión en la primera fecha del año en el contexto actual.",
        "syntax": "OPENINGBALANCEYEAR(<expression>,<dates> or <calendar>[,<filter>][,<year_end_date>])",
    },
    "OR": {
        "description": "Comprueba si uno de los argumentos es TRUE devolver TRUE .",
        "syntax": "OR(<logical1>,<logical2>)",
    },
    "ORDERBY": {
        "description": "Define las columnas que determinan el criterio de ordenación dentro de cada una de las particiones de una función de ventana.",
        "syntax": "ORDERBY ( [<orderBy_expression>[, <order>[, <orderBy_expression>[, <order>]] …]] )",
    },
    "PARALLELPERIOD": {
        "description": "Devuelve una tabla que contiene una columna de fechas que representa un período paralelo a las fechas de la columna de fechas especificadas, en el contexto actual, con las fechas desplazadas un número de intervalos hacia delante en el tiempo o hacia atrás en el tiempo.",
        "syntax": "PARALLELPERIOD(<dates> or <calendar>,<number_of_intervals>,<interval>)",
    },
    "PARTITIONBY": {
        "description": "Define las columnas que se usan para particionar el parámetro relation de una función de ventana.",
        "syntax": "PARTITIONBY ( [<partitionBy_columnName>[, partitionBy_columnName [, …]]] )",
    },
    "PATH": {
        "description": "Devuelve una cadena de texto delimitada con los identificadores de all los elementos primarios del identificador actual.",
        "syntax": "PATH(<ID_columnName>, <parent_columnName>)",
    },
    "PATHCONTAINS": {
        "description": "Devuelve TRUE if existe el item especificado en el path especificado.",
        "syntax": "PATHCONTAINS(<path>, <item>)",
    },
    "PATHITEM": {
        "description": "Devuelve el elemento en el position especificado de una cadena resultante de la evaluación de una función PATH.",
        "syntax": "PATHITEM(<path>, <position>[, <type>])",
    },
    "PATHITEMREVERSE": {
        "description": "Devuelve el elemento en el position especificado de una cadena resultante de la evaluación de una función PATH.",
        "syntax": "PATHITEMREVERSE(<path>, <position>[, <type>])",
    },
    "PATHLENGTH": {
        "description": "Devuelve el número de elementos primarios al elemento especificado en un PATH resultado determinado, incluido el propio.",
        "syntax": "PATHLENGTH(<path>)",
    },
    "PDURATION": {
        "description": "Devuelve el número de períodos requeridos por una inversión para alcanzar un valor especificado.",
        "syntax": "PDURATION(<rate>, <pv>, <fv>)",
    },
    "PERCENTILE.EXC": {
        "description": "Devuelve el percentil k-ésimo de los valores de un intervalo, donde k está en el intervalo 0..1, exclusivo.",
        "syntax": "PERCENTILE.EXC(<column>, <k>)",
    },
    "PERCENTILE.INC": {
        "description": "Devuelve el percentil k-ésimo de los valores de un intervalo, donde k está en el intervalo 0..1, ambos incluidos.",
        "syntax": "PERCENTILE.INC(<column>, <k>)",
    },
    "PERCENTILEX.EXC": {
        "description": "Devuelve el número de percentil de una expresión evaluada para cada fila de una tabla.",
        "syntax": "PERCENTILEX.EXC(<table>, <expression>, k)",
    },
    "PERCENTILEX.INC": {
        "description": "Devuelve el número de percentil de una expresión evaluada para cada fila de una tabla.",
        "syntax": "PERCENTILEX.INC(<table>, <expression>;, k)",
    },
    "PERMUT": {
        "description": "Devuelve el número de permutaciones de un número determinado de objetos que se pueden seleccionar a partir de objetos numéricos.",
        "syntax": "PERMUT(number, number_chosen)",
    },
    "PI": {
        "description": "Devuelve el valor de Pi, 3,14159265358979, exacto a 15 dígitos.",
    },
    "PMT": {
        "description": "Calcula el pago de un préstamo basado en pagos constantes y una tasa de interés constante.",
        "syntax": "PMT(<rate>, <nper>, <pv>[, <fv>[, <type>]])",
    },
    "POISSON.DIST": {
        "description": "Devuelve la distribución de Poisson.",
        "syntax": "POISSON.DIST(x,mean,cumulative)",
    },
    "POWER": {
        "description": "Devuelve el resultado de un número elevado a una potencia.",
        "syntax": "POWER(<number>, <power>)",
    },
    "PPMT": {
        "description": "Devuelve el pago de la entidad de seguridad durante un período determinado para una inversión basada en pagos periódicos, constantes y un tipo de interés constante.",
        "syntax": "PPMT(<rate>, <per>, <nper>, <pv>[, <fv>[, <type>]])",
    },
    "PREVIOUS": {
        "description": "Solo se usa en cálculos visuales. Recupera un valor en la fila anterior de un eje de la matriz visual.",
    },
    "PREVIOUSDAY": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas que representan el día anterior a la primera fecha de la columna dates, en el contexto actual.",
        "syntax": "PREVIOUSDAY(<dates> or <calendar>)",
    },
    "PREVIOUSMONTH": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas del mes anterior, según la primera fecha de la columna dates, en el contexto actual.",
        "syntax": "PREVIOUSMONTH(<dates> or <calendar>)",
    },
    "PREVIOUSQUARTER": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas del trimestre anterior, según la primera fecha de la columna dates, en el contexto actual.",
        "syntax": "PREVIOUSQUARTER(<dates> or <calendar>)",
    },
    "PREVIOUSWEEK": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas que representan la semana anterior a la primera fecha de la columna dates, en el contexto actual.",
    },
    "PREVIOUSYEAR": {
        "description": "Devuelve una tabla que contiene una columna de todas las fechas del año anterior, dada la última fecha de la columna dates, en el contexto actual.",
        "syntax": "PREVIOUSYEAR(<dates> or <calendar>[,<year_end_date>])",
    },
    "PRICE": {
        "description": "Devuelve el precio por valor nominal de $100 de una seguridad que paga intereses periódicos.",
        "syntax": "PRICE(<settlement>, <maturity>, <rate>, <yld>, <redemption>, <frequency>[, <basis>])",
    },
    "PRICEDISC": {
        "description": "Devuelve el precio por valor nominal de 100 USD de una seguridad con descuento.",
        "syntax": "PRICEDISC(<settlement>, <maturity>, <discount>, <redemption>[, <basis>])",
    },
    "PRICEMAT": {
        "description": "Devuelve el precio por valor nominal de $100 de un valor de seguridad que paga intereses al vencimiento.",
        "syntax": "PRICEMAT(<settlement>, <maturity>, <issue>, <rate>, <yld>[, <basis>])",
    },
    "PRODUCT": {
        "description": "Devuelve el producto de los números de una columna.",
        "syntax": "PRODUCT(<column>)",
    },
    "PRODUCTX": {
        "description": "Devuelve el producto de una expresión evaluada para cada fila de una tabla.",
        "syntax": "PRODUCTX(<table>, <expression>)",
    },
    "PV": {
        "description": "Calcula el valor actual de un préstamo o una inversión, basándose en una tasa de interés constante.",
        "syntax": "PV(<rate>, <nper>, <pmt>[, <fv>[, <type>]])",
    },
    "QUARTER": {
        "description": "Devuelve el trimestre como un número comprendido entre 1 y 4.",
        "syntax": "QUARTER(<date>)",
    },
    "QUOTIENT": {
        "description": "Realiza la división y devuelve solo la parte entera del resultado de la división.",
        "syntax": "QUOTIENT(<numerator>, <denominator>)",
    },
    "RADIANS": {
        "description": "Convierte grados en radianes.",
        "syntax": "RADIANS(angle)",
    },
    "RAND": {
        "description": "Devuelve un número aleatorio mayor o igual que 0 y menor que 1, distribuido uniformemente.",
    },
    "RANDBETWEEN": {
        "description": "Devuelve un número aleatorio en el intervalo entre dos números que especifique.",
        "syntax": "RANDBETWEEN(<bottom>,<top>)",
    },
    "RANGE": {
        "description": "Devuelve un intervalo de filas dentro del eje especificado, en relación con la fila actual. Acceso directo para WINDOW.",
    },
    "RANK": {
        "description": "Devuelve la clasificación de una fila dentro del intervalo especificado.",
    },
    "RANK.EQ": {
        "description": "Devuelve la clasificación de un número en una lista de números.",
        "syntax": "RANK.EQ(<value>, <columnName>[, <order>])",
    },
    "RANKX": {
        "description": "Devuelve la clasificación de un número en una lista de números para cada fila del argumento table .",
        "syntax": "RANKX(<table>, <expression>[, <value>[, <order>[, <ties>]]])",
    },
    "RATE": {
        "description": "Devuelve la tasa de interés por período de anualidad.",
        "syntax": "RATE(<nper>, <pmt>, <pv>[, <fv>[, <type>[, <guess>]]])",
    },
    "RECEIVED": {
        "description": "Devuelve el importe recibido al vencimiento de una seguridad totalmente invertida.",
        "syntax": "RECEIVED(<settlement>, <maturity>, <investment>, <discount>[, <basis>])",
    },
    "RELATED": {
        "description": "Devuelve un valor relacionado de otra tabla.",
        "syntax": "RELATED(<column>)",
    },
    "RELATEDTABLE": {
        "description": "Evalúa una expresión de tabla en un contexto modificado por los filtros especificados.",
        "syntax": "RELATEDTABLE(<tableName>)",
    },
    "REMOVEFILTERS": {
        "description": "Borra los filtros de las tablas o columnas especificadas.",
        "syntax": "REMOVEFILTERS([<table> | <column>[, <column>[, <column>[,…]]]])",
    },
    "REPLACE": {
        "description": "REPLACE reemplaza parte de una cadena de texto, en función del número de caracteres que especifique, por una cadena de texto diferente.",
        "syntax": "REPLACE(<old_text>, <start_num>, <num_chars>, <new_text>)",
    },
    "REPT": {
        "description": "Repite el texto un número determinado de veces.",
        "syntax": "REPT(<text>, <num_times>)",
    },
    "RIGHT": {
        "description": "RIGHT devuelve el último carácter o caracteres de una cadena de texto, en",
        "syntax": "RIGHT(<text>, <num_chars>)",
    },
    "ROLLUP": {
        "description": "Modifica el comportamiento de SUMMARIZE agregando filas de acumulación al resultado en las columnas definidas por el parámetro groupBy_columnName.",
    },
    "ROLLUPADDISSUBTOTAL": {
        "description": "Modifica el comportamiento de SUMMARIZECOLUMNS agregando filas de acumulación o subtotal al resultado en función de las columnas de groupBy_columnName.",
        "syntax": "ROLLUPADDISSUBTOTAL ( [<grandtotalFilter>], <groupBy_columnName>, <name> [, [<groupLevelFilter>] [, <groupBy_columnName>, <name> [, [<groupLevelFilter>] [, … ] ] ] ] )",
    },
    "ROLLUPGROUP": {
        "description": "Modifica el comportamiento de SUMMARIZE y SUMMARIZECOLUMNS agregando filas de acumulación al resultado en las columnas definidas por el parámetro groupBy_columnName.",
        "syntax": "ROLLUPGROUP ( <groupBy_columnName> [, <groupBy_columnName> [, … ] ] )",
    },
    "ROLLUPISSUBTOTAL": {
        "description": "Empareja los grupos acumulativos con la columna agregada por ROLLUPADDISSUBTOTAL dentro de una expresión ADDMISSINGITEMS.",
        "syntax": "ROLLUPISSUBTOTAL ( [<grandTotalFilter>], <groupBy_columnName>, <isSubtotal_columnName> [, [<groupLevelFilter>] [, <groupBy_columnName>, <isSubtotal_columnName> [, [<groupLevelFilter>] [, … ] ] ] ] )",
    },
    "ROUND": {
        "description": "Redondea un número al número especificado de dígitos.",
        "syntax": "ROUND(<number>, <num_digits>)",
    },
    "ROUNDDOWN": {
        "description": "Redondea un número hacia abajo, hacia cero.",
        "syntax": "ROUNDDOWN(<number>, <num_digits>)",
    },
    "ROUNDUP": {
        "description": "Redondea un número hacia arriba, lejos de 0 (cero).",
        "syntax": "ROUNDUP(<number>, <num_digits>)",
    },
    "ROW": {
        "description": "Devuelve una tabla con una sola fila que contiene valores resultantes de las expresiones dadas a cada columna.",
        "syntax": "ROW(<name>, <expression>[[,<name>, <expression>]…])",
    },
    "ROWNUMBER": {
        "description": "Devuelve la clasificación única de una fila dentro del intervalo especificado.",
        "syntax": "ROWNUMBER ( [<relation> or <axis>][, <orderBy>][, <blanks>][, <partitionBy>][, <matchBy>][, <reset>] )",
    },
    "RRI": {
        "description": "Devuelve una tasa de interés equivalente para el crecimiento de una inversión.",
        "syntax": "RRI(<nper>, <pv>, <fv>)",
    },
    "RUNNINGSUM": {
        "description": "Devuelve una suma en ejecución calculada a lo largo del eje especificado de la matriz visual.",
    },
    "SAMEPERIODLASTYEAR": {
        "description": "Devuelve una tabla que contiene una columna de fechas desplazadas un año atrás a partir de las fechas de la columna de fechas especificada, en el contexto actual.",
        "syntax": "SAMEPERIODLASTYEAR(<dates> or <calendar>)",
    },
    "SAMPLE": {
        "description": "Devuelve un ejemplo de N filas de la tabla especificada.",
        "syntax": "SAMPLE(<n_value>, <table>, <orderBy_expression>, [<order>[, <orderBy_expression>, [<order>]]…])",
    },
    "SEARCH": {
        "description": "Devuelve el número del carácter en el que se encuentra por primera vez un carácter específico o una cadena de texto, leyendo de izquierda a derecha.",
        "syntax": "SEARCH(<find_text>, <within_text>[, [<start_num>][, <NotFoundValue>]])",
    },
    "SECOND": {
        "description": "Devuelve los segundos de un valor de tiempo, como un número comprendido entre 0 y 59.",
        "syntax": "SECOND(<time>)",
    },
    "SELECTCOLUMNS": {
        "description": "Agrega columnas calculadas a la tabla o expresión de tabla especificadas.",
        "syntax": "SELECTCOLUMNS(<Table>, [<Name>], <Expression>, [<Name>], …)",
    },
    "SELECTEDMEASURE": {
        "description": "Se usa en expresiones para los elementos de cálculo para hacer referencia a la medida que se encuentra en contexto.",
    },
    "SELECTEDMEASUREFORMATSTRING": {
        "description": "Se usa en expresiones para los elementos de cálculo para recuperar la cadena de formato de la medida que se encuentra en contexto.",
    },
    "SELECTEDMEASURENAME": {
        "description": "Se usa en expresiones para los elementos de cálculo para determinar la medida que se encuentra en contexto por nombre.",
    },
    "SELECTEDVALUE": {
        "description": "Devuelve el valor cuando el contexto de columnName se ha filtrado solo a un valor distinto. De lo contrario, devuelve alternateResult.",
        "syntax": "SELECTEDVALUE(<columnName>[, <alternateResult>])",
    },
    "SIGN": {
        "description": "Determina el signo de un número, el resultado de un cálculo o un valor de una columna.",
        "syntax": "SIGN(<number>)",
    },
    "SIN": {
        "description": "Devuelve el seno del ángulo especificado.",
        "syntax": "SIN(number)",
    },
    "SINH": {
        "description": "Devuelve el seno hiperbólico de un número.",
        "syntax": "SINH(number)",
    },
    "SLN": {
        "description": "Devuelve la depreciación de línea recta de un activo durante un período.",
        "syntax": "SLN(<cost>, <salvage>, <life>)",
    },
    "SQRT": {
        "description": "Devuelve la raíz cuadrada de un número.",
        "syntax": "SQRT(<number>)",
    },
    "SQRTPI": {
        "description": "Devuelve la raíz cuadrada de (número * pi).",
        "syntax": "SQRTPI(number)",
    },
    "STARTOFMONTH": {
        "description": "Devuelve la primera fecha del mes en el contexto actual de la columna de fechas especificada.",
        "syntax": "STARTOFMONTH(<dates> or <calendar>)",
    },
    "STARTOFQUARTER": {
        "description": "Devuelve la primera fecha del trimestre en el contexto actual de la columna de fechas especificada.",
        "syntax": "STARTOFQUARTER(<dates> or <calendar>)",
    },
    "STARTOFWEEK": {
        "description": "Devuelve la primera fecha de la semana en el contexto actual de la columna de fechas especificada.",
    },
    "STARTOFYEAR": {
        "description": "Devuelve la primera fecha del año en el contexto actual de la columna de fechas especificada.",
        "syntax": "STARTOFYEAR(<dates> or <calendar>)",
    },
    "STDEV.P": {
        "description": "Devuelve la desviación estándar de toda la población.",
        "syntax": "STDEV.P(<ColumnName>)",
    },
    "STDEV.S": {
        "description": "Devuelve la desviación estándar de una población de muestra.",
        "syntax": "STDEV.S(<ColumnName>)",
    },
    "STDEVX.P": {
        "description": "Devuelve la desviación estándar de toda la población.",
        "syntax": "STDEVX.P(<table>, <expression>)",
    },
    "STDEVX.S": {
        "description": "Devuelve la desviación estándar de una población de muestra.",
        "syntax": "STDEVX.S(<table>, <expression>)",
    },
    "SUBSTITUTE": {
        "description": "Reemplaza el texto existente por texto nuevo en una cadena de texto.",
        "syntax": "SUBSTITUTE(<text>, <old_text>, <new_text>, <instance_num>)",
    },
    "SUBSTITUTEWITHINDEX": {
        "description": "Devuelve una tabla que representa un punto y coma izquierdo de las dos tablas proporcionadas como argumentos.",
        "syntax": "SUBSTITUTEWITHINDEX(<table>, <indexColumnName>, <indexColumnsTable>, [<orderBy_expression>, [<order>][, <orderBy_expression>, [<order>]]…])",
    },
    "SUM": {
        "description": "Agrega todos los números de una columna.",
        "syntax": "SUM(<column>)",
    },
    "SUMMARIZE": {
        "description": "Devuelve una tabla de resumen de los totales solicitados en un conjunto de grupos.",
        "syntax": "SUMMARIZE (<table>, <groupBy_columnName>[, <groupBy_columnName>]…[, <name>, <expression>]…)",
    },
    "SUMMARIZECOLUMNS": {
        "description": "Devuelve una tabla de resumen sobre un conjunto de grupos.",
        "syntax": "SUMMARIZECOLUMNS( <groupBy_columnName> [, < groupBy_columnName >]…, [<filterTable>]…[, <name>, <expression>]…)",
    },
    "SUMX": {
        "description": "Devuelve la suma de una expresión evaluada para cada fila de una tabla. APPROXIMATEDISTINCTCOUNT",
        "syntax": "SUMX(<table>, <expression>)",
    },
    "SWITCH": {
        "description": "Evalúa una expresión con una lista de valores y devuelve una de varias expresiones de resultado posibles.",
        "syntax": "SWITCH(<expression>, <value>, <result>[, <value>, <result>]…[, <else>])",
    },
    "SYD": {
        "description": "Devuelve la depreciación de dígitos de los años de un activo durante un período especificado.",
        "syntax": "SYD(<cost>, <salvage>, <life>, <per>)",
    },
    "T.DIST": {
        "description": "Devuelve la distribución t de cola izquierda de Student.",
        "syntax": "T.DIST(X,Deg_freedom,Cumulative)",
    },
    "T.DIST.2T": {
        "description": "Devuelve la distribución t de Student de dos colas.",
        "syntax": "T.DIST.2T(X,Deg_freedom)",
    },
    "T.DIST.RT": {
        "description": "Devuelve la distribución t de Student de cola derecha.",
        "syntax": "T.DIST.RT(X,Deg_freedom)",
    },
    "T.INV": {
        "description": "Devuelve el inverso de cola izquierda de la distribución t de Student.",
        "syntax": "T.INV(Probability,Deg_freedom)",
    },
    "TABLEOF": {
        "description": "Devuelve una referencia a la tabla asociada a una columna, medida o calendario especificadas.",
    },
    "TAN": {
        "description": "Devuelve la tangente del ángulo especificado.",
        "syntax": "TAN(number)",
    },
    "TANH": {
        "description": "Devuelve la tangente hiperbólica de un número.",
        "syntax": "TANH(number)",
    },
    "TBILLEQ": {
        "description": "Devuelve el rendimiento equivalente a bonos para una factura del Tesoro.",
        "syntax": "TBILLEQ(<settlement>, <maturity>, <discount>)",
    },
    "TBILLPRICE": {
        "description": "Devuelve el precio por valor nominal de $100 para una factura del Tesoro.",
        "syntax": "TBILLPRICE(<settlement>, <maturity>, <discount>)",
    },
    "TBILLYIELD": {
        "description": "Devuelve el rendimiento de una factura del Tesoro.",
        "syntax": "TBILLYIELD(<settlement>, <maturity>, <pr>)",
    },
    "TIME": {
        "description": "Convierte horas, minutos y segundos dados como números a una hora en formato datetime.",
        "syntax": "TIME(hour, minute, second)",
    },
    "TIMEVALUE": {
        "description": "Convierte una hora en formato de texto a una hora en formato datetime.",
        "syntax": "TIMEVALUE(time_text)",
    },
    "TOCSV": {
        "description": "Devuelve una tabla como una cadena en formato CSV.",
        "syntax": "TOCSV(<Table>, [MaxRows], [Delimiter], [IncludeHeaders])",
    },
    "TODAY": {
        "description": "Devuelve la fecha actual.",
    },
    "TOJSON": {
        "description": "Devuelve una tabla como una cadena en formato JSON. BLANK Se aplica a:     columna Calculada     tabla calculada    Medida       cálculo visual",
        "syntax": "TOJSON(<Table>, [MaxRows])",
    },
    "TOPN": {
        "description": "Devuelve las N primeras filas de la tabla especificada.",
        "syntax": "TOPN(<N_Value>, <Table>, <OrderBy_Expression>, [<Order>[, <OrderBy_Expression>, [<Order>]]…])",
    },
    "TOTALMTD": {
        "description": "Evalúa el valor de la expresión para el mes hasta la fecha, en el contexto actual.",
        "syntax": "TOTALMTD(<expression>,<dates> or <calendar>[,<filter>])",
    },
    "TOTALQTD": {
        "description": "Evalúa el valor de la expresión para las fechas del trimestre hasta la fecha, en el contexto actual.",
        "syntax": "TOTALQTD(<expression>,<dates>[,<filter>])",
    },
    "TOTALWTD": {
        "description": "Evalúa el valor de la expresión para la semana hasta la fecha, en el contexto actual.",
    },
    "TOTALYTD": {
        "description": "Evalúa el valor de año a fecha de la expresión en el contexto actual. CLOSINGBALANCEWEEK Se aplica a:     Columna          calculadaTabla         calculadaMedir         Cálculo visual",
        "syntax": "TOTALYTD(<expression>,<dates> or <calendar>[,<filter>][,<year_end_date>])",
    },
    "TREATAS": {
        "description": "Aplica el resultado de una expresión de tabla como filtros a columnas de una tabla no relacionada.",
        "syntax": "TREATAS(table_expression, <column>[, <column>[, <column>[,…]]]} )",
    },
    "TRIM": {
        "description": "Quita todos los espacios del texto, excepto los espacios únicos entre palabras.",
        "syntax": "TRIM(<text>)",
    },
    "TRUE": {
        "description": "Devuelve el valor lógico TRUE .",
    },
    "TRUNC": {
        "description": "Trunca un número en un entero quitando la parte decimal o fraccionaria del número.",
        "syntax": "TRUNC(<number>,<num_digits>)",
    },
    "UNICHAR": {
        "description": "Devuelve el carácter Unicode al que hace referencia el valor numérico.",
        "syntax": "UNICHAR(number)",
    },
    "UNICODE": {
        "description": "Devuelve el código numérico correspondiente al primer carácter de la cadena de texto.",
        "syntax": "UNICODE( <Text> )",
    },
    "UNION": {
        "description": "Crea una tabla de unión (combinación) a partir de un par de tablas.",
        "syntax": "UNION(<table_expression1>, <table_expression2> [,<table_expression>]…)",
    },
    "UPPER": {
        "description": "Convierte una cadena de texto en todas las letras mayúsculas.",
        "syntax": "UPPER (<text>)",
    },
    "USERCULTURE": {
        "description": "Devuelve la configuración regional del usuario actual.",
    },
    "USERELATIONSHIP": {
        "description": "Especifica la relación que se va a usar en un cálculo específico como la que existe entre columnName1 y columnName2.",
        "syntax": "USERELATIONSHIP(<columnName1>,<columnName2>)",
    },
    "USERNAME": {
        "description": "Devuelve el nombre de dominio y el nombre de usuario de las credenciales que se proporcionan al sistema en el momento de la conexión.",
    },
    "USEROBJECTID": {
        "description": "Devuelve el identificador de objeto o el SID del usuario actual.",
    },
    "USERPRINCIPALNAME": {
        "description": "Devuelve el nombre principal de usuario.",
    },
    "UTCNOW": {
        "description": "Devuelve la fecha y hora UTC actuales.",
    },
    "UTCTODAY": {
        "description": "Devuelve la fecha UTC actual.",
    },
    "VALUE": {
        "description": "Convierte una cadena de texto que representa un número en un número.",
        "syntax": "VALUE(<text>)",
    },
    "VALUES": {
        "description": "Devuelve una tabla de una columna que contiene los valores distintos de la tabla o columna especificadas.",
        "syntax": "VALUES(<TableNameOrColumnName>)",
    },
    "VAR.P": {
        "description": "Devuelve la varianza de toda la población.",
        "syntax": "VAR.P(<columnName>)",
    },
    "VAR.S": {
        "description": "Devuelve la varianza de un rellenado de muestra.",
        "syntax": "VAR.S(<columnName>)",
    },
    "VARX.P": {
        "description": "Devuelve la varianza de toda la población.",
        "syntax": "VARX.P(<table>, <expression>)",
    },
    "VARX.S": {
        "description": "Devuelve la varianza de un rellenado de muestra.",
        "syntax": "VARX.S(<table>, <expression>)",
    },
    "VDB": {
        "description": "Devuelve la depreciación de un activo durante cualquier período especificado, incluidos los períodos parciales, mediante el método de doble disminución del saldo o algún otro método que especifique.",
        "syntax": "VDB(<cost>, <salvage>, <life>, <start_period>, <end_period>[, <factor>[, <no_switch>]])",
    },
    "WEEKDAY": {
        "description": "Devuelve un número de 1 a 7 que identifica el día de la semana de una fecha.",
        "syntax": "WEEKDAY(<date>, <return_type>)",
    },
    "WEEKNUM": {
        "description": "Devuelve el número de semana de la fecha y el año especificados según el valor de return_type.",
        "syntax": "WEEKNUM(<date>[, <return_type>])",
    },
    "WINDOW": {
        "description": "Devuelve varias filas que se colocan dentro del intervalo especificado. ALL",
        "syntax": "WINDOW ( from[, from_type], to[, to_type][, <relation> or <axis>][, <orderBy>][, <blanks>][, <partitionBy>][, <matchBy>][, <reset>] )",
    },
    "XIRR": {
        "description": "Devuelve la tasa interna de retorno para un calendario de flujos de efectivo que no es necesariamente periódico.",
        "syntax": "XIRR(<table>, <values>, <dates>, [, <guess>[, <alternateResult>]])",
    },
    "XNPV": {
        "description": "Devuelve el valor actual de una programación de flujos de efectivo que no es necesariamente periódica.",
        "syntax": "XNPV(<table>, <values>, <dates>, <rate>)",
    },
    "YEAR": {
        "description": "Devuelve el año de una fecha como un entero de cuatro dígitos en el intervalo 1900-9999.",
        "syntax": "YEAR(<date>)",
    },
    "YEARFRAC": {
        "description": "Calcula la fracción del año representada por el número de días enteros entre dos fechas.",
        "syntax": "YEARFRAC(<start_date>, <end_date>, <basis>)",
    },
    "YIELD": {
        "description": "Devuelve el rendimiento de una seguridad que paga intereses periódicos.",
        "syntax": "YIELD(<settlement>, <maturity>, <rate>, <pr>, <redemption>, <frequency>[, <basis>])",
    },
    "YIELDDISC": {
        "description": "Devuelve el rendimiento anual de una seguridad con descuento.",
        "syntax": "YIELDDISC(<settlement>, <maturity>, <pr>, <redemption>[, <basis>])",
    },
    "YIELDMAT": {
        "description": "Devuelve el rendimiento anual de una seguridad que paga intereses al vencimiento.",
        "syntax": "YIELDMAT(<settlement>, <maturity>, <issue>, <rate>, <pr>[, <basis>])",
    },
}


def get_relevant_dax_docs(measures_df):
    """
    Scan DAX expressions from a PBIXRay measures DataFrame and return
    documentation for only the DAX functions actually used.
    
    Args:
        measures_df: DataFrame with columns including "Expression" (DAX code)
    Returns:
        String with formatted DAX function reference for the system prompt
    """
    import re
    
    # Collect all DAX expressions
    all_dax = ""
    for _, row in measures_df.iterrows():
        all_dax += " " + str(row.get("Expression", ""))
    
    all_dax_upper = all_dax.upper()
    
    # Find which DAX functions appear in the expressions
    used_functions = {}
    for fname, info in DAX_FUNCTIONS.items():
        # Match function name followed by ( or as standalone keyword
        pattern = r"\b" + re.escape(fname) + r"\s*\("
        if re.search(pattern, all_dax_upper):
            used_functions[fname] = info
    
    # Also check for keywords without parens: VAR, RETURN, TRUE, FALSE, BLANK
    for keyword in ["VAR", "RETURN", "TRUE", "FALSE", "BLANK", "IN"]:
        if keyword in all_dax_upper and keyword in DAX_FUNCTIONS:
            used_functions[keyword] = DAX_FUNCTIONS[keyword]
    
    if not used_functions:
        return "(No DAX functions detected in measures)"
    
    # Format as reference text
    lines = []
    lines.append(f"=== DAX FUNCTION REFERENCE ({len(used_functions)} functions used in this .pbix) ===")
    lines.append("")
    for fname in sorted(used_functions.keys()):
        info = used_functions[fname]
        lines.append(f"### {fname}")
        if info.get("syntax"):
            lines.append(f"Syntax: {info['syntax']}")
        lines.append(f"Description: {info['description']}")
        lines.append("")
    
    return "\n".join(lines)
