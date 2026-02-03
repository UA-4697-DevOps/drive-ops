package http

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"

	"trip-service/internal/domain"
	"trip-service/internal/service"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type TripHandler struct {
	svc service.TripServiceInterface
}

func NewTripHandler(svc service.TripServiceInterface) *TripHandler {
	return &TripHandler{svc: svc}
}

// CreateTrip handles POST /trips
// @Summary      Create a new trip
// @Description  Creates a new trip request with pickup and dropoff locations
// @Tags         trips
// @Accept       json
// @Produce      json
// @Param        trip  body      domain.Trip  true  "Trip request payload"
// @Success      201   {object}  domain.Trip
// @Failure      400   {object}  map[string]string  "Invalid request body or missing required fields"
// @Failure      500   {object}  map[string]string  "Internal server error"
// @Router       /trips [post]
func (h *TripHandler) CreateTrip(w http.ResponseWriter, r *http.Request) {
	var trip domain.Trip
	if err := json.NewDecoder(r.Body).Decode(&trip); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if err := h.svc.CreateTrip(r.Context(), &trip); err != nil {
		// FIX: Changed from ErrInvalidTripData to ErrInvalidCreateTripData
		if errors.Is(err, domain.ErrInvalidCreateTripData) {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		log.Printf("Failed to create trip: %v", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	if err := json.NewEncoder(w).Encode(trip); err != nil {
		log.Printf("Failed to encode response: %v", err)
	}
}

// GetTrip handles GET /trips/{id}
// @Summary      Get trip by ID
// @Description  Retrieves trip details by its unique identifier
// @Tags         trips
// @Accept       json
// @Produce      json
// @Param        id   path      string  true  "Trip UUID"
// @Success      200  {object}  domain.Trip
// @Failure      400  {object}  map[string]string  "Invalid UUID format"
// @Failure      404  {object}  map[string]string  "Trip not found"
// @Failure      500  {object}  map[string]string  "Internal server error"
// @Router       /trips/{id} [get]
func (h *TripHandler) GetTrip(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	id, err := uuid.Parse(idStr)
	if err != nil {
		http.Error(w, "Invalid UUID format", http.StatusBadRequest)
		return
	}

	trip, err := h.svc.GetTrip(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrTripNotFound) {
			http.Error(w, "Trip not found", http.StatusNotFound)
			return
		}
		
		log.Printf("Failed to get trip %s: %v", id, err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(trip); err != nil {
		log.Printf("Failed to encode response: %v", err)
	}
}

// AssignDriver handles PATCH /trips/{id}/assign-driver
// @Summary      Assign driver to trip
// @Description  Assigns a driver to an existing trip and updates trip status
// @Tags         trips
// @Accept       json
// @Produce      json
// @Param        id      path      string                       true  "Trip UUID"
// @Param        driver  body      domain.AssignDriverRequest   true  "Driver assignment payload"
// @Success      200     {object}  map[string]string            "Driver assigned successfully"
// @Failure      400     {object}  map[string]string            "Invalid UUID or request body"
// @Failure      404     {object}  map[string]string            "Trip not found"
// @Failure      409     {object}  map[string]string            "Trip is no longer available for assignment"
// @Failure      500     {object}  map[string]string            "Internal server error"
// @Router       /trips/{id}/assign-driver [patch]
func (h *TripHandler) AssignDriver(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	tripID, err := uuid.Parse(idStr)
	if err != nil {
		http.Error(w, "Invalid Trip UUID format", http.StatusBadRequest)
		return
	}

	var req domain.AssignDriverRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	err = h.svc.AssignDriver(r.Context(), tripID, req.DriverID)
	if err != nil {
		switch {
		// FIX: Changed from ErrInvalidTripData to ErrInvalidID
		case errors.Is(err, domain.ErrInvalidID):
			http.Error(w, err.Error(), http.StatusBadRequest)
		case errors.Is(err, domain.ErrTripNotFound):
			http.Error(w, "Trip not found", http.StatusNotFound)
		case errors.Is(err, domain.ErrInvalidTripStatus):
			http.Error(w, err.Error(), http.StatusConflict)
		default:
			log.Printf("Failed to assign driver: %v", err)
			http.Error(w, "Internal server error", http.StatusInternalServerError)
		}
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(map[string]string{"status": "driver_assigned"}); err != nil {
		log.Printf("Failed to encode assign-driver response: %v", err)
	}
}

// HealthCheck handles GET /health
// @Summary      Health check
// @Description  Returns service health status
// @Tags         health
// @Produce      json
// @Success      200  {object}  map[string]string
// @Router       /health [get]
func (h *TripHandler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write([]byte(`{"status":"ok"}`)); err != nil {
		log.Printf("Failed to write health response: %v", err)
	}
}
