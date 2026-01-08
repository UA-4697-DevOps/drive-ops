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
func (h *TripHandler) CreateTrip(w http.ResponseWriter, r *http.Request) {
	var trip domain.Trip
	if err := json.NewDecoder(r.Body).Decode(&trip); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if err := h.svc.CreateTrip(r.Context(), &trip); err != nil {
		// Check for validation error to return 400 Bad Request
		if errors.Is(err, domain.ErrInvalidTripData) {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		// Log actual error for debugging and return 500
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
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(trip); err != nil {
		log.Printf("Failed to encode response: %v", err)
	}
}

// AssignDriver handles PATCH /trips/{id}/assign-driver
func (h *TripHandler) AssignDriver(w http.ResponseWriter, r *http.Request) {
	// 1. Parse Trip ID from URL
	idStr := chi.URLParam(r, "id")
	tripID, err := uuid.Parse(idStr)
	if err != nil {
		http.Error(w, "Invalid Trip UUID format", http.StatusBadRequest)
		return
	}

	// 2. Decode Request Body (driver_id)
	var req domain.AssignDriverRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// 3. Call Service Layer
	err = h.svc.AssignDriver(r.Context(), tripID, req.DriverID)
	if err != nil {
		switch {
		case errors.Is(err, domain.ErrInvalidTripData):
			// Return 400 Bad Request for validation errors
			http.Error(w, err.Error(), http.StatusBadRequest)
		case errors.Is(err, domain.ErrTripNotFound):
			http.Error(w, "Trip not found", http.StatusNotFound)
		case errors.Is(err, domain.ErrInvalidTripStatus):
			// 409 Conflict for "already taken" or "invalid state"
			http.Error(w, "Trip is no longer available for assignment", http.StatusConflict)
		default:
			log.Printf("Failed to assign driver: %v", err)
			http.Error(w, "Internal server error", http.StatusInternalServerError)
		}
		return
	}

	// 4. Return Success
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "driver_assigned"})
}

// HealthCheck handles GET /health
func (h *TripHandler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write([]byte(`{"status":"ok"}`)); err != nil {
		log.Printf("Failed to write health response: %v", err)
	}
}
