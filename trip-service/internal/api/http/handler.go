package http

import (
	"encoding/json"
	"errors"
	"net/http"
	"trip-service/internal/domain"
	"trip-service/internal/service"

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
		http.Error(w, err.Error(), http.StatusUnprocessableEntity)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(trip)
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
		if errors.Is(err, service.ErrTripNotFound) {
			http.Error(w, "Trip not found", http.StatusNotFound)
		} else {
			http.Error(w, "Internal server error", http.StatusInternalServerError)
		}
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(trip)
}

// GET /health
func (h *TripHandler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ok"}`))
}
