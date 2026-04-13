# Yarig.ai + Yarig.Telegram — Product Blueprint

Documento vivo para aprender todas las funcionalidades de Yarig.ai, convertirlas en operativa movil por Telegram y usar ese conocimiento como base de una nueva version de la plataforma con look and feel moderno e IA nativa.

## Vision

Yarig.Telegram debe funcionar como una capa operativa completa sobre Yarig.ai:

- operar desde movil sin abrir la web;
- reducir cada flujo frecuente a comandos, botones o resummenes inteligentes;
- descubrir y documentar endpoints y reglas reales de negocio;
- detectar fricciones de UX de la plataforma actual;
- convertir lo aprendido en especificacion para una Yarig.ai renovada.

La nueva Yarig.ai no deberia ser solo una web mas bonita. Debe ser un sistema de trabajo asistido por IA: menos navegacion, mas contexto, mas decisiones sugeridas y mas automatizacion.

## Principios de Producto

1. Mobile first real: si una accion se hace a diario, debe poder completarse desde Telegram en menos de tres pasos.
2. IA como copiloto operativo: el sistema debe resumir, priorizar, detectar bloqueos y proponer siguientes acciones.
3. Paridad funcional progresiva: cada modulo de Yarig.ai debe tener estado de cobertura en Telegram.
4. Descubrimiento continuo: cada endpoint descubierto se documenta con parametros, respuesta, uso y riesgos.
5. Diseño desde workflows reales: la futura UI saldra de lo que el equipo realmente hace, no de la arquitectura historica de pantallas.

## Mapa de Modulos

| Modulo Yarig.ai | Uso principal | Cobertura Telegram | Estado |
|---|---|---:|---|
| Dashboard | Vision general del dia | Parcial via `/estado`, `/yarig`, `/resumen_diario` | Mejorar |
| Mis tareas | Crear, iniciar, pausar, finalizar tareas | Alta via `/yarig`, `/tarea`, `/iniciar`, `/pausar`, `/finalizar` | Operativo |
| Historial tareas | Revisar actividad pasada | Media via `/historial` con parsing HTML | Endurecer |
| Peticiones | Pedir, leer, aceptar tareas | Alta via `/pedir`, `/peticiones` y botones | Operativo |
| Jornada | Entrada, salida, extras | Alta via `/fichar`, `/extras`, automatizaciones | Operativo |
| Score / puntos | Puntuacion actual y mensual | Alta via `/personal`, `/score`, `/puntos`, `/stats` | Operativo |
| Productividad equipo | Ranking y dedicacion | Alta via `/ranking`, `/dedicacion` | Operativo |
| Equipo | Listado, ranking, dedicacion y peticiones | Alta via `/equipo`, `/equipo_lista`, `/pedir` | Operativo |
| Proyectos | Buscar proyecto y crear tareas asociadas | Media via `/proyectos`, `/proyecto`, `/tarea Proyecto :: desc` | En curso |
| Clientes | Clientes y oportunidades | Media via `/clientes`, `/cliente` | En curso |
| Notificaciones | Avisos recientes | Media via `/notificaciones` | Mejorar acciones |
| Muro | Feed, emergencias, actividad | Baja | Pendiente |
| Reuniones | Reuniones y eventos | Sin cobertura | Pendiente |
| Perfil | Datos del usuario, estado, preferencias | Media via `/personal` | En curso |
| Admin | Gestion interna | Sin cobertura | Pendiente |
| Facturacion | Bills, entradas/salidas | Baja via `/finanzas` con probe web | Descubrir endpoints |
| Marca/RRSS | Social media / marca | Baja via `/marca` con probe web | Descubrir endpoints |
| Consejo IA | Consultas a sillas IA y actas | Alta via `/consejo`, `/consulta`, `/actas` | Operativo |

## Cobertura Actual en Telegram

### Panel Operativo

Comandos:

- `/yarig`: panel del dia con tareas y botones inline.
- `/estado`: jornada, tarea activa y XP.
- `/resumen_diario`: resumen de estado, peticiones y notificaciones.
- `/help`: ayuda general.

Botones existentes:

- actualizar panel;
- abrir peticiones;
- ver avisos;
- ver estado;
- lanzar resumen;
- onboarding;
- offboarding;
- iniciar, pausar y finalizar tareas.

Huecos:

- falta un panel unico tipo "Home movil" con tareas, peticiones, bloqueos, foco actual, equipo y recomendaciones IA;
- falta botonera por modulo: Proyectos, Clientes, Equipo, Reuniones, Muro.

### Tareas

Comandos:

- `/tarea <descripcion>`;
- `/tarea Proyecto :: descripcion`;
- `/random [proyecto]`;
- `/iniciar [n]`;
- `/pausar`;
- `/finalizar [n]`;
- `/mision_dia`;
- `/onboarding`;
- `/offboarding`.

Endpoints usados:

- `tasks/json_get_current_day_tasks_and_journey_info`;
- `tasks/json_add_tasks`;
- `tasks/json_get_and_open_task`;
- `tasks/json_close_task`.

Pendiente:

- editar tarea desde Telegram;
- borrar tarea desde Telegram;
- cambiar proyecto de una tarea;
- cambiar estimacion;
- listar tareas por proyecto, cliente, fecha o persona;
- crear tareas multiples desde un texto largo con ayuda IA.

### Jornada

Comandos:

- `/fichar`;
- `/fichar salida`;
- `/extras`;
- `/extras fin`.

Endpoints usados:

- `clocking/json_add_clocking`;
- `clocking_extra/json_add_clocking_extra`.

Pendiente:

- ver historico de fichajes;
- corregir fichaje desde Telegram si la API lo permite;
- resumen semanal de horas;
- detectar automaticamente "estas trabajando sin tarea activa".

### Score, Estadisticas y Puntos

Comandos:

- `/score`;
- `/stats`;
- `/puntos`.

Endpoints usados:

- `score/json_user_score`;
- `personal/json_get_user_days`;
- `personal/json_get_scoring`.

Pendiente:

- explicar por que se ganan o pierden puntos;
- alertas de riesgo de score;
- recomendaciones IA para recuperar racha;
- comparativa semanal/mensual.

### Equipo y Productividad

Comandos:

- `/equipo`;
- `/ranking`;
- `/dedicacion`;
- `/pedir <nombre> <tarea>`.

Endpoints usados:

- `user/json_get_customers_and_mates_like`;
- `productivity/json_get_team_by_order_or_rank`;
- `tasks/json_get_newer_company_tasks`;
- `tasks/json_add_request`.

Pendiente:

- ficha de companero: `/persona Carlos`;
- disponibilidad real: trabajando, reunion, casa, ausente;
- carga por persona;
- deteccion de bloqueos;
- sugerir a quien pedir una tarea.

### Peticiones

Comandos:

- `/peticiones`;
- `/pedir`.

Botones:

- aceptar;
- marcar como leida;
- elegir prioridad al enviar.

Endpoints usados:

- `tasks/json_get_unread_requests_by_user`;
- `tasks/json_update_state_task_request`;
- `tasks/json_add_open_task_from_task_request`;
- `tasks/json_add_request`.

Pendiente:

- ver detalle completo de peticion;
- responder con comentario;
- rechazar/devolver;
- filtrar por prioridad;
- bandeja de enviadas;
- avisos proactivos de urgencias.

### Proyectos

Comandos:

- `/proyectos [texto]`;
- `/proyecto <texto>`;
- `/tarea Proyecto :: descripcion`;

Endpoints usados:

- `projects/json_get_projects_like_by_customer_and_order`.

Pendiente prioritario:

- `/proyecto <nombre>`: ficha de proyecto inicial;
- tareas de hoy por proyecto;
- historial por proyecto;
- cliente asociado;
- proximas acciones sugeridas por IA;
- resumen ejecutivo para movil;
- crear tarea desde ficha de proyecto;
- buscar proyecto sin depender solo de cliente Admira.

### Clientes

Cobertura actual:

- `/clientes [texto]` busca clientes con `user/json_get_customers_and_mates_like`;
- `/cliente <nombre>` muestra ficha movil inicial con proyectos y actividad de hoy;
- proyectos ya puede recibir formato `Cliente :: filtro`.

Pendiente prioritario:

- tareas, oportunidades, reuniones, facturacion y estado por cliente;
- resumen IA de cliente.

### Notificaciones y Muro

Comandos:

- `/notificaciones`.

Endpoints usados:

- `system_notification/json_get_user_notifications`.

Pendiente:

- marcar notificacion como leida;
- marcar todas como leidas;
- descubrir feed de muro;
- acciones inline por notificacion;
- alertas proactivas configurables.

### Consejo IA

Comandos:

- `/consejo`;
- `/consulta`;
- `/actas`;
- `/acta`;
- `/cancelar`.

Cobertura:

- mesa de 8 sillas IA;
- targets por consejo completo, operativo, creativo, parejas y silla individual;
- actas locales;
- dispatch a bots individuales de consejeros cuando estan configurados.

Pendiente:

- vincular respuestas del consejo con tareas Yarig;
- convertir acta en plan de accion;
- consultar contexto real de proyecto/cliente antes de responder;
- usar consejo como capa de decision para la nueva Yarig.ai.

## Backlog de Comandos Propuestos

### Prioridad 1 — Operativa diaria

| Comando | Objetivo |
|---|---|
| `/home` | Panel unico movil: foco, tareas, peticiones, equipo, score, sugerencias IA |
| `/proyecto <texto>` | Ficha de proyecto con tareas, historico y siguientes acciones |
| `/cliente <texto>` | Ficha de cliente con proyectos y actividad |
| `/editar <n>` | Editar descripcion/proyecto/estimacion de tarea |
| `/borrar <n>` | Eliminar tarea |
| `/leer_avisos` | Marcar notificaciones como leidas |
| `/bloqueos` | Detectar tareas paradas, peticiones urgentes y personas bloqueadas |

### Prioridad 2 — Inteligencia operativa

| Comando | Objetivo |
|---|---|
| `/siguiente` | Recomendar la siguiente accion |
| `/plan_dia` | Crear plan del dia desde tareas, peticiones y calendario |
| `/resumir_proyecto <texto>` | Resumen IA del proyecto |
| `/resumir_cliente <texto>` | Resumen IA del cliente |
| `/delegar <tarea>` | Sugerir destinatario y enviar peticion |
| `/limpiar` | Convertir texto desordenado en tareas/proyectos |

### Prioridad 3 — Plataforma futura

| Comando | Objetivo |
|---|---|
| `/feedback_yarig <texto>` | Registrar friccion o idea para la nueva plataforma |
| `/blueprint` | Resumen del estado de cobertura funcional |
| `/descubrir <modulo>` | Checklist guiada para mapear endpoints y pantallas |
| `/mockup <modulo>` | Generar propuesta de pantalla moderna IA-first |

## Endpoints Conocidos

Ver tambien `docs/yarig_api_map.md`.

### Alta confianza

- `registration/login`;
- `tasks/json_get_current_day_tasks_and_journey_info`;
- `tasks/json_add_tasks`;
- `tasks/json_get_and_open_task`;
- `tasks/json_close_task`;
- `clocking/json_add_clocking`;
- `clocking_extra/json_add_clocking_extra`;
- `score/json_user_score`;
- `user/json_get_customers_and_mates_like`;
- `projects/json_get_projects_like_by_customer_and_order`;
- `tasks/json_get_unread_requests_by_user`;
- `tasks/json_update_state_task_request`;
- `tasks/json_add_open_task_from_task_request`;
- `tasks/json_add_request`;
- `system_notification/json_get_user_notifications`;
- `productivity/json_get_team_by_order_or_rank`;
- `tasks/json_get_newer_company_tasks`;
- `personal/json_get_user_days`;
- `personal/json_get_scoring`.

### Por confirmar

- `tasks/json_update_task`;
- `tasks/json_delete_task`;
- `tasks/json_get_task_request`;
- `tasks/json_get_unread_requests_by_user_and_priority`;
- `system_notification/json_change_notification_state`;
- `system_notification/json_wall_all_read`;
- `working_state/json_change_state`;
- endpoints de clientes;
- endpoints de reuniones;
- endpoints de muro;
- endpoints de facturacion;
- endpoints de perfil;
- endpoints de admin;
- endpoints de marca/RRSS.

## Gaps Para Descubrimiento

1. Clientes: listado, busqueda, ficha, proyectos, actividad.
2. Proyectos: detalle, tareas por proyecto, estado, cliente, responsables.
3. Reuniones: listado, detalle, crear o actualizar.
4. Muro: feed, emergencias, comentarios, marcar leido.
5. Facturacion: permisos, listados, resumen ejecutivo.
6. Perfil: estado, preferencias, jornada, ubicacion.
7. Admin: usuarios, roles, permisos.
8. Marca/RRSS: calendario, publicaciones, tareas asociadas.

## Blueprint de la Nueva Yarig.ai

### Concepto

Una plataforma de productividad de equipo con IA integrada, donde cada usuario empieza el dia en un cockpit claro:

- foco actual;
- tareas del dia;
- urgencias;
- peticiones;
- energia/score;
- equipo y disponibilidad;
- recomendaciones IA;
- contexto de proyectos y clientes.

### Pantallas Propuestas

1. Home IA
   - "Que hago ahora"
   - bloqueos
   - mision activa
   - peticiones urgentes
   - resumen del equipo

2. Misiones
   - tablero de tareas por estado
   - start/pause/finish instantaneo
   - IA para dividir tareas grandes
   - estimacion y aprendizaje de tiempos

3. Proyecto
   - ficha viva
   - tareas abiertas
   - historial
   - personas implicadas
   - resumen IA
   - siguientes acciones

4. Cliente
   - salud del cliente
   - proyectos
   - actividad reciente
   - oportunidades
   - riesgos

5. Equipo
   - dedicacion actual
   - disponibilidad
   - ranking sano, no punitivo
   - bloqueos
   - sugerencias de delegacion

6. Consejo IA
   - sala de decision
   - actas
   - recomendaciones convertibles en tareas
   - contexto automatico de cliente/proyecto

## Plan de Trabajo

### Fase 1 — Inventario y Paridad

- Completar mapa de endpoints.
- Marcar cobertura por modulo.
- Crear comandos basicos para Proyectos y Clientes.
- Documentar workflows reales.

### Fase 2 — Telegram Como Operativa Completa

- Crear `/home`.
- Mejorar `/proyecto` y `/cliente`.
- Acciones inline por notificacion y peticion.
- Panel de bloqueos.
- Resumen IA diario y semanal.

### Fase 3 — IA Nativa

- Recomendador de siguiente accion.
- Generador de plan del dia.
- Asistente de delegacion.
- Resumen de proyecto/cliente.
- Consejo IA con contexto real.

### Fase 4 — Nueva Plataforma

- Wireframes por modulo.
- Design system.
- Arquitectura API moderna.
- Prototipo web IA-first.
- Migracion gradual desde Yarig.ai actual.

## Proxima Iteracion Recomendada

Construir el modulo **Proyectos + Clientes** porque es el mayor puente entre "hacer tareas" y "entender el contexto de negocio".

Primeros entregables:

1. `/proyecto <texto>` con ficha ampliada.
2. `/cliente <texto>` con proyectos asociados.
3. Documento de endpoints descubiertos para clientes.
4. Panel `/home` con acceso rapido a Proyecto, Cliente, Equipo, Peticiones y Consejo.
