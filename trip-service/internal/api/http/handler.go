package http

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"

	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/domain"
	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/service"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

type TripHandler struct {
	svc *service.TripService
}

func NewTripHandler(svc *service.TripService) *TripHandler {
	return &TripHandler{svc: svc}
}

// POST /trips
func (h *TripHandler) CreateTrip(w http.ResponseWriter, r *http.Request) {
	var trip domain.Trip
	if err := json.NewDecoder(r.Body).Decode(&trip); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if err := h.svc.CreateTrip(r.Context(), &trip); err != nil {
		if errors.Is(err, service.ErrInvalidInput) {
			http.Error(w, "Invalid input: pickup and dropoff locations are required", http.StatusBadRequest)
			return
		}
		// Log actual error for debugging, return generic message to client
		log.Printf("Failed to create trip: %v", err)
		http.Error(w, "Failed to create trip", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	if err := json.NewEncoder(w).Encode(trip); err != nil {
		log.Printf("Failed to encode response: %v", err)
	}
}

// GET /trips/{id}
func (h *TripHandler) GetTrip(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	id, err := uuid.Parse(idStr)
	if err != nil {
		http.Error(w, "Invalid UUID format", http.StatusBadRequest)
		return
	}

	trip, err := h.svc.GetTrip(r.Context(), id)
	if err != nil {
		http.Error(w, "Trip not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(trip); err != nil {
		log.Printf("Failed to encode response: %v", err)
	}
}

// GET /health
func (h *TripHandler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write([]byte(`{"status":"ok"}`)); err != nil {
		log.Printf("Failed to write health response: %v", err)
	}
}
