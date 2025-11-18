import java.util.*;
import java.time.LocalTime;
import java.text.SimpleDateFormat;

// Enumeraciones
enum EstadoCita {
    PENDIENTE, CONFIRMADA, CANCELADA, COMPLETADA
}

enum DiaSemana {
    LUNES, MARTES, MIERCOLES, JUEVES, VIERNES, SABADO, DOMINGO
}

// Clase para representar franjas horarias
class TimeSlot {
    private Date fecha;
    private LocalTime horaInicio;
    private LocalTime horaFin;
    private boolean disponible;
    
    public TimeSlot(Date fecha, LocalTime horaInicio, LocalTime horaFin) {
        this.fecha = fecha;
        this.horaInicio = horaInicio;
        this.horaFin = horaFin;
        this.disponible = true;
    }
    
    public boolean isDisponible() { return disponible; }
    public void setDisponible(boolean disponible) { this.disponible = disponible; }
    public Date getFecha() { return fecha; }
    public LocalTime getHoraInicio() { return horaInicio; }
    public LocalTime getHoraFin() { return horaFin; }
    
    @Override
    public String toString() {
        SimpleDateFormat sdf = new SimpleDateFormat("dd/MM/yyyy");
        return sdf.format(fecha) + " " + horaInicio + " - " + horaFin;
    }
}

// Clase Cita
class Cita {
    private String id;
    private Date fechaHora;
    private EstadoCita estado;
    private String pacienteId;
    private String doctorId;
    private String motivo;
    
    public Cita(String id, Date fechaHora, EstadoCita estado) {
        this.id = id;
        this.fechaHora = fechaHora;
        this.estado = estado;
    }
    
    public String getId() { return id; }
    public Date getFechaHora() { return fechaHora; }
    public EstadoCita getEstado() { return estado; }
    public void setEstado(EstadoCita estado) { this.estado = estado; }
    public String getPacienteId() { return pacienteId; }
    public void setPacienteId(String pacienteId) { this.pacienteId = pacienteId; }
    public String getDoctorId() { return doctorId; }
    public void setDoctorId(String doctorId) { this.doctorId = doctorId; }
    
    @Override
    public String toString() {
        SimpleDateFormat sdf = new SimpleDateFormat("dd/MM/yyyy HH:mm");
        return "Cita{" + "id='" + id + '\'' + ", fechaHora=" + sdf.format(fechaHora) + ", estado=" + estado + '}';
    }
}

// Clase Doctor
class Doctor {
    private String id;
    private String nombre;
    private String especialidad;
    private String telefono;
    private String email;
    
    public Doctor(String id, String nombre, String especialidad) {
        this.id = id;
        this.nombre = nombre;
        this.especialidad = especialidad;
    }
    
    public String getId() { return id; }
    public String getNombre() { return nombre; }
    public String getEspecialidad() { return especialidad; }
    public String getTelefono() { return telefono; }
    public void setTelefono(String telefono) { this.telefono = telefono; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    
    @Override
    public String toString() {
        return "Doctor{" + "id='" + id + '\'' + ", nombre='" + nombre + '\'' + ", especialidad='" + especialidad + '\'' + '}';
    }
}

// Clase BaseDatos
class BaseDatos {
    public void enviarConfirmacion(Cita cita) {
        System.out.println("📊 [Paso 23] BaseDatos: Enviando confirmación para cita: " + cita.getId());
        guardarCita(cita);
    }
    
    private void guardarCita(Cita cita) {
        System.out.println("💾 [Paso 24] BaseDatos: Guardando cita en base de datos...");
        
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
        
        System.out.println("✅ [Paso 25] BaseDatos: Cita guardada exitosamente - confirmacionGuardado");
        System.out.println("📨 [Paso 26] BaseDatos: Notificación enviada y registrada - notificacionEnviada");
    }
}

// Clase Agenda
class Agenda {
    private Map<String, Doctor> doctores;
    private Map<String, List<TimeSlot>> horariosDoctores;
    
    public Agenda() {
        this.doctores = new HashMap<>();
        this.horariosDoctores = new HashMap<>();
        inicializarDatosPrueba();
    }
    
    private void inicializarDatosPrueba() {
        doctores.put("D001", new Doctor("D001", "Dr. García", "Cardiología"));
        doctores.put("D002", new Doctor("D002", "Dra. Martínez", "Pediatría"));
        doctores.put("D003", new Doctor("D003", "Dr. López", "Dermatología"));
        
        Date fecha = new Date();
        List<TimeSlot> horariosDrGarcia = Arrays.asList(
            new TimeSlot(fecha, LocalTime.of(9, 0), LocalTime.of(10, 0)),
            new TimeSlot(fecha, LocalTime.of(11, 0), LocalTime.of(12, 0)),
            new TimeSlot(fecha, LocalTime.of(15, 0), LocalTime.of(16, 0))
        );
        
        List<TimeSlot> horariosDraMartinez = Arrays.asList(
            new TimeSlot(fecha, LocalTime.of(8, 0), LocalTime.of(9, 0)),
            new TimeSlot(fecha, LocalTime.of(10, 0), LocalTime.of(11, 0))
        );
        
        horariosDoctores.put("D001", horariosDrGarcia);
        horariosDoctores.put("D002", horariosDraMartinez);
        horariosDoctores.put("D003", new ArrayList<>());
    }
    
    public List<Doctor> obtenerDoctores() {
        System.out.println("📋 [Paso 5] Agenda: Obteniendo lista de doctores...");
        return new ArrayList<>(doctores.values());
    }
    
    public List<TimeSlot> verificarDisponibilidad(String doctorId) {
        System.out.println("🕐 [Paso 12] Agenda: Verificando disponibilidad para doctor: " + doctorId);
        
        List<TimeSlot> horariosDisponibles = horariosDoctores.getOrDefault(doctorId, new ArrayList<>())
            .stream()
            .filter(TimeSlot::isDisponible)
            .collect(ArrayList::new, ArrayList::add, ArrayList::addAll);
        
        System.out.println("✅ [Paso 13] Agenda: " + horariosDisponibles.size() + " horarios disponibles encontrados - horariosDisponibles");
        return horariosDisponibles;
    }
    
    public boolean reservarHorario(Map<String, Object> datosCita) {
        System.out.println("🔒 [Paso 19] Agenda: Reservando horario...");
        
        String doctorId = (String) datosCita.get("doctorId");
        TimeSlot horario = (TimeSlot) datosCita.get("horario");
        
        if (horario != null && horario.isDisponible()) {
            horario.setDisponible(false);
            System.out.println("✅ [Paso 20] Agenda: Horario reservado exitosamente - horarioReservado");
            return true;
        }
        
        System.out.println("❌ [Paso 20] Agenda: No se pudo reservar el horario");
        return false;
    }
}

// Clase SistemaNotificaciones
class SistemaNotificaciones {
    private BaseDatos baseDatos;
    
    public SistemaNotificaciones() {
        this.baseDatos = new BaseDatos();
    }
    
    public void notificarCitaCreada(Cita cita) {
        System.out.println("📧 [Paso 22] SistemaNotificaciones: Notificando cita creada: " + cita.getId());
        baseDatos.enviarConfirmacion(cita);
        
        ServicioCita servicio = new ServicioCita();
        servicio.confirmacionCompleta(cita.getId());
    }
}

// Clase ServicioCita
class ServicioCita {
    private Agenda agenda;
    private BaseDatos baseDatos;
    
    public ServicioCita() {
        this.agenda = new Agenda();
        this.baseDatos = new BaseDatos();
    }
    
    public List<Doctor> consultarDoctoresDisponibles() {
        System.out.println("👨‍⚕️ [Paso 4] Servicio: Consultando doctores disponibles...");
        List<Doctor> doctores = agenda.obtenerDoctores();
        System.out.println("✅ [Paso 7] Servicio: " + doctores.size() + " doctores disponibles - doctoresDisponibles");
        return doctores;
    }
    
    public List<TimeSlot> obtenerHorariosDisponibles(String doctorId) {
        System.out.println("🕐 [Paso 11] Servicio: Obteniendo horarios para doctor: " + doctorId);
        List<TimeSlot> horarios = agenda.verificarDisponibilidad(doctorId);
        System.out.println("📅 [Paso 14] Servicio: Retornando " + horarios.size() + " horarios - listaHorarios");
        return horarios;
    }
    
    public Cita crearCita(Map<String, Object> datosCita) {
        System.out.println("📝 [Paso 18] Servicio: Creando nueva cita...");
        
        boolean horarioReservado = agenda.reservarHorario(datosCita);
        
        if (horarioReservado) {
            Cita cita = new Cita(
                "C" + System.currentTimeMillis(),
                new Date(),
                EstadoCita.CONFIRMADA
            );
            cita.setPacienteId((String) datosCita.get("pacienteId"));
            cita.setDoctorId((String) datosCita.get("doctorId"));
            
            System.out.println("✅ [Paso 21] Servicio: Cita creada exitosamente - citaCreada: " + cita.getId());
            return cita;
        }
        
        System.out.println("❌ [Paso 21] Servicio: No se pudo crear la cita");
        return null;
    }
    
    public void confirmacionCompleta(String citaId) {
        System.out.println("🎉 [Paso 27] Servicio: Confirmación completa recibida para cita: " + citaId + " - confirmacionCompleta");
    }
}

// Clase ControladorCita
class ControladorCita {
    private ServicioCita servicioCita;
    private SistemaNotificaciones sistemaNotificaciones;
    
    public ControladorCita() {
        this.servicioCita = new ServicioCita();
        this.sistemaNotificaciones = new SistemaNotificaciones();
    }
    
    public void obtenerDoctores() {
        System.out.println("👨‍⚕️ [Paso 3] Controlador: Obteniendo lista de doctores...");
        List<Doctor> doctores = servicioCita.consultarDoctoresDisponibles();
        
        InterfazUsuario interfaz = InterfazUsuario.getInstance();
        interfaz.mostrarDoctores(doctores);
    }
    
    public void verDisponibilidad(String doctorId) {
        System.out.println("🔍 [Paso 10] Controlador: Verificando disponibilidad para doctor: " + doctorId);
        
        List<TimeSlot> horarios = servicioCita.obtenerHorariosDisponibles(doctorId);
        
        if (horarios != null && !horarios.isEmpty()) {
            InterfazUsuario interfaz = InterfazUsuario.getInstance();
            interfaz.mostrarHorarios(horarios);
        } else {
            InterfazUsuario interfaz = InterfazUsuario.getInstance();
            interfaz.mostrarError("No hay horarios disponibles para este doctor");
        }
    }
    
    public void confirmarCita(Map<String, Object> datosCita) {
        System.out.println("✅ [Paso 17] Controlador: Confirmando cita con datos proporcionados...");
        
        Cita citaCreada = servicioCita.crearCita(datosCita);
        
        if (citaCreada != null) {
            sistemaNotificaciones.notificarCitaCreada(citaCreada);
            
            InterfazUsuario interfaz = InterfazUsuario.getInstance();
            interfaz.mostrarConfirmacion("Cita agendada exitosamente para: " + 
                                       new SimpleDateFormat("dd/MM/yyyy HH:mm").format(new Date()));
        } else {
            InterfazUsuario interfaz = InterfazUsuario.getInstance();
            interfaz.mostrarError("No se pudo agendar la cita. Intente nuevamente.");
        }
    }
}

// Clase InterfazUsuario
class InterfazUsuario {
    private static InterfazUsuario instance;
    private ControladorCita controlador;
    private Scanner scanner;
    
    private InterfazUsuario() {
        this.controlador = new ControladorCita();
        this.scanner = new Scanner(System.in);
    }
    
    public static InterfazUsuario getInstance() {
        if (instance == null) {
            instance = new InterfazUsuario();
        }
        return instance;
    }
    
    public void mostrarFormularioAgendarCita(Paciente paciente) {
        System.out.println("\n=== FORMULARIO DE AGENDAMIENTO DE CITA ===");
        System.out.println("Paciente: " + paciente.getNombre());
        System.out.println("Email: " + paciente.getEmail());
        
        if (validarDatos(paciente)) {
            controlador.obtenerDoctores();
        } else {
            System.out.println("❌ Error: Datos del paciente inválidos");
        }
    }
    
    private boolean validarDatos(Paciente paciente) {
        System.out.println("🔍 [Paso 2] Interfaz: Validando datos del paciente...");
        return paciente.getEmail() != null && !paciente.getEmail().isEmpty() && paciente.getEmail().contains("@");
    }
    
    public void mostrarDoctores(List<Doctor> doctores) {
        System.out.println("\n=== DOCTORES DISPONIBLES ===");
        System.out.println("✅ [Paso 8] Interfaz: Mostrando " + doctores.size() + " doctores disponibles - mostrarDoctores");
        
        for (int i = 0; i < doctores.size(); i++) {
            System.out.println((i + 1) + ". " + doctores.get(i).getNombre() + " - " + doctores.get(i).getEspecialidad() + " (ID: " + doctores.get(i).getId() + ")");
        }
        
        System.out.print("\nSeleccione el número del doctor: ");
        int seleccion = scanner.nextInt();
        scanner.nextLine();
        
        if (seleccion > 0 && seleccion <= doctores.size()) {
            String doctorId = doctores.get(seleccion - 1).getId();
            procesarSeleccionDoctor(doctorId);
        } else {
            System.out.println("❌ Selección inválida");
        }
    }
    
    public void procesarSeleccionDoctor(String doctorId) {
        System.out.println("🎯 [Paso 9] Interfaz: Procesando selección de doctor: " + doctorId);
        controlador.verDisponibilidad(doctorId);
    }
    
    public void mostrarHorarios(List<TimeSlot> horarios) {
        System.out.println("\n=== HORARIOS DISPONIBLES ===");
        System.out.println("📅 [Paso 15] Interfaz: Mostrando " + horarios.size() + " horarios disponibles - mostrarHorarios");
        
        for (int i = 0; i < horarios.size(); i++) {
            System.out.println((i + 1) + ". " + horarios.get(i));
        }
        
        System.out.print("\nSeleccione el número del horario: ");
        int seleccion = scanner.nextInt();
        scanner.nextLine();
        
        if (seleccion > 0 && seleccion <= horarios.size()) {
            procesarSeleccionHorario(horarios.get(seleccion - 1));
        } else {
            System.out.println("❌ Selección inválida");
        }
    }
    
    public void procesarSeleccionHorario(TimeSlot horario) {
        System.out.println("⏰ [Paso 16] Interfaz: Procesando selección de horario: " + horario.getHoraInicio());
        
        Map<String, Object> datosCita = new HashMap<>();
        datosCita.put("horario", horario);
        datosCita.put("pacienteId", "P001");
        datosCita.put("doctorId", "D001");
        datosCita.put("fecha", new Date());
        
        controlador.confirmarCita(datosCita);
    }
    
    public void mostrarConfirmacion(String mensajeConfirmacion) {
        System.out.println("\n🎉 [Paso 28] Interfaz: Mostrando confirmación al usuario - mostrarConfirmacion");
        System.out.println("=========================================");
        System.out.println("✅ " + mensajeConfirmacion);
        System.out.println("=========================================");
        
        Paciente paciente = new Paciente("P001", "Juan Pérez", "juan@email.com", "555-1234");
        paciente.confirmacionRecibida(mensajeConfirmacion);
    }
    
    public void mostrarError(String mensajeError) {
        System.out.println("\n❌ [Flujo Alternativo] Interfaz: Mostrando error - mostrarError");
        System.out.println("ERROR: " + mensajeError);
        
        Paciente paciente = new Paciente("P001", "Juan Pérez", "juan@email.com", "555-1234");
        paciente.errorRecibido(mensajeError);
    }
}

// Clase Paciente
class Paciente {
    private String id;
    private String nombre;
    private String email;
    private String telefono;
    
    public Paciente(String id, String nombre, String email, String telefono) {
        this.id = id;
        this.nombre = nombre;
        this.email = email;
        this.telefono = telefono;
    }
    
    public void solicitarAgendarCita() {
        System.out.println("🎫 [Paso 1] Paciente " + nombre + " solicita agendar cita - solicitarAgendarCita");
        InterfazUsuario interfaz = InterfazUsuario.getInstance();
        interfaz.mostrarFormularioAgendarCita(this);
    }
    
    public void confirmacionRecibida(String mensaje) {
        System.out.println("📩 [Paso 29] Paciente recibe confirmación: " + mensaje + " - confirmacionRecibida");
    }
    
    public void errorRecibido(String mensaje) {
        System.out.println("❌ [Paso 13 - Flujo Alternativo] Paciente recibe error: " + mensaje + " - errorRecibido");
    }
    
    public String getId() { return id; }
    public String getNombre() { return nombre; }
    public String getEmail() { return email; }
    public String getTelefono() { return telefono; }
}

// Clase Principal
public class SistemaGestionCitas {
    public static void main(String[] args) {
        System.out.println("=== SISTEMA DE GESTIÓN DE CITAS MÉDICAS ===\n");
        
        // Crear paciente e iniciar el proceso
        Paciente paciente = new Paciente("P001", "Juan Pérez", "juan@email.com", "555-1234");
        
        // Paso 1: Iniciar el proceso de agendar cita
        paciente.solicitarAgendarCita();
        
        System.out.println("\n=== PROCESO COMPLETADO ===");
    }
}
