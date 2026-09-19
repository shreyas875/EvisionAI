function ChargingAvailabilityOptions(options) {
    this.options = options;
  }
  
  ChargingAvailabilityOptions.prototype.go = function() {
    const options = this.options;
  
    return new Promise(function(fulfill, reject) {
      if (!hasOwnProperties(options, [ 'chargingAvailability', 'key' ])) {
        reject('chargingAvailability call is missing required properties.');
        return;
      }
  
      fetchResponse(formatUrl(options), fulfill, reject);
    });
  
    function fetchResponse(url, fulfill, reject) {
      fetch(url, {
        method: 'GET',
        mode: 'cors',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      .then(function(response) {
        parseResponse(response, fulfill, reject);
      })
      .catch(function(error) {
        reject(error);
      });
    }
  
    function formatUrl(options) {
      return 'https://api.tomtom.com/search/2/chargingAvailability.json?' +
        'chargingAvailability=' +  encodeURIComponent(options.chargingAvailability) + '&' +
        'key=' + encodeURIComponent(options.key);
    }
  
    function hasOwnProperties(options, properties) {
      if (options == null)
        return false;
  
      for(const property of properties)
        if (!options.hasOwnProperty(property))
          return false;
  
      return true;
    }
  
    function parseResponse(response, fulfill, reject) {
      response
        .json()
        .then(function(obj) {
          if (!obj.hasOwnProperty('error'))
            fulfill(obj);
          else
            reject(obj.error.description);
        })
        .catch(function(error) {
          reject(error);
        });
    }
  }
  
  function chargingAvailability(options) {
    return new ChargingAvailabilityOptions(options);
  }

  // Enhanced EVisionAI ML-based charging availability with waiting time predictions
  class EVisionAIChargingAvailability {
    constructor(apiBaseUrl = 'http://localhost:8000') {
      this.apiBaseUrl = apiBaseUrl;
      this.cache = new Map();
      this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    }

    /**
     * Get ML-predicted waiting times for all stations
     * @param {Object} options - Configuration options
     * @param {string} options.location - User location (lat,lon or address)
     * @param {string} [options.weather_condition='sunny'] - Weather condition
     * @param {number} [options.weather_severity=0.5] - Weather severity (0-1)
     * @param {number} [options.traffic_level=0.5] - Traffic level (0-1)
     * @param {boolean} [options.is_holiday=false] - Is holiday
     * @returns {Promise<Object>} Prediction results with color-coded wait times
     */
    async getMLPredictions(options) {
      const cacheKey = JSON.stringify(options);
      const cached = this.cache.get(cacheKey);
      
      if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
        return cached.data;
      }

      try {
        const params = new URLSearchParams({
          location: options.location,
          weather_condition: options.weather_condition || 'sunny',
          weather_severity: (options.weather_severity || 0.5).toString(),
          traffic_level: (options.traffic_level || 0.5).toString(),
          is_holiday: (options.is_holiday || false).toString()
        });

        const response = await fetch(`${this.apiBaseUrl}/stations/predict_all_stations?${params}`);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        // Cache the result
        this.cache.set(cacheKey, {
          data: data,
          timestamp: Date.now()
        });

        return data;
      } catch (error) {
        console.error('Error fetching ML predictions:', error);
        throw error;
      }
    }

    /**
     * Get prediction for a specific station
     * @param {Object} options - Configuration options
     * @param {number} options.station_id - Station ID
     * @param {number} [options.hour] - Hour of day (0-23)
     * @param {number} [options.day_of_week] - Day of week (0-6)
     * @param {string} [options.weather_condition='sunny'] - Weather condition
     * @param {number} [options.weather_severity=0.5] - Weather severity (0-1)
     * @param {number} [options.traffic_level=0.5] - Traffic level (0-1)
     * @param {boolean} [options.is_holiday=false] - Is holiday
     * @returns {Promise<Object>} Station-specific prediction
     */
    async getStationPrediction(options) {
      try {
        const params = new URLSearchParams({
          station_id: options.station_id.toString(),
          weather_condition: options.weather_condition || 'sunny',
          weather_severity: (options.weather_severity || 0.5).toString(),
          traffic_level: (options.traffic_level || 0.5).toString(),
          is_holiday: (options.is_holiday || false).toString()
        });

        if (options.hour !== undefined) {
          params.append('hour', options.hour.toString());
        }
        if (options.day_of_week !== undefined) {
          params.append('day_of_week', options.day_of_week.toString());
        }

        const response = await fetch(`${this.apiBaseUrl}/stations/predict_waiting?${params}`);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
      } catch (error) {
        console.error('Error fetching station prediction:', error);
        throw error;
      }
    }

    /**
     * Train the ML model (admin function)
     * @returns {Promise<Object>} Training results
     */
    async trainModel() {
      try {
        const response = await fetch(`${this.apiBaseUrl}/stations/train_model`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
      } catch (error) {
        console.error('Error training model:', error);
        throw error;
      }
    }

    /**
     * Get color-coded wait time display
     * @param {number} waitTimeMinutes - Wait time in minutes
     * @returns {Object} Display information with color and text
     */
    getWaitTimeDisplay(waitTimeMinutes) {
      if (waitTimeMinutes < 5) {
        return {
          color: '#00ff00', // Green
          category: 'green',
          text: `${waitTimeMinutes.toFixed(1)} min`,
          description: 'Low wait time'
        };
      } else if (waitTimeMinutes < 15) {
        return {
          color: '#ffaa00', // Yellow/Orange
          category: 'yellow',
          text: `${waitTimeMinutes.toFixed(1)} min`,
          description: 'Moderate wait time'
        };
      } else {
        return {
          color: '#ff0000', // Red
          category: 'red',
          text: `${waitTimeMinutes.toFixed(1)} min`,
          description: 'High wait time'
        };
      }
    }

    /**
     * Display predictions on a map (for integration with existing map systems)
     * @param {Object} predictions - Prediction results from getMLPredictions
     * @param {Function} addMarkerCallback - Callback to add markers to map
     */
    displayPredictionsOnMap(predictions, addMarkerCallback) {
      if (!predictions.results) return;

      predictions.results.forEach(station => {
        const waitDisplay = this.getWaitTimeDisplay(station.predicted_wait_time_minutes);
        
        const markerInfo = {
          position: {
            lat: station.latitude,
            lng: station.longitude
          },
          title: `${station.station_name} - ${waitDisplay.text}`,
          icon: {
            url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
              <svg width="30" height="40" viewBox="0 0 30 40" xmlns="http://www.w3.org/2000/svg">
                <path d="M15 0C6.7 0 0 6.7 0 15c0 15 15 25 15 25s15-10 15-25c0-8.3-6.7-15-15-15z" 
                      fill="${waitDisplay.color}" stroke="#ffffff" stroke-width="2"/>
                <text x="15" y="22" text-anchor="middle" fill="white" font-size="12" font-weight="bold">⚡</text>
              </svg>
            `)}`,
            scaledSize: new google.maps.Size(30, 40),
            anchor: new google.maps.Point(15, 40)
          },
          infoWindow: {
            content: `
              <div style="padding: 10px; max-width: 300px;">
                <h3 style="margin: 0 0 10px 0; color: #0078ff; font-size: 16px;">${station.station_name}</h3>
                <p style="margin: 5px 0; font-size: 14px;">
                  <strong>Predicted Wait:</strong> 
                  <span style="color: ${waitDisplay.color}; font-weight: bold;">${waitDisplay.text}</span>
                  <span style="color: #666; font-size: 12px;">(${waitDisplay.description})</span>
                </p>
                <p style="margin: 5px 0; font-size: 14px;"><strong>Distance:</strong> ${station.distance_km} km</p>
                <p style="margin: 5px 0; font-size: 14px;"><strong>Chargers:</strong> ${station.charger_types}</p>
                <p style="margin: 5px 0; font-size: 14px;"><strong>Ports:</strong> ${station.num_ports}</p>
                <p style="margin: 5px 0; font-size: 14px;"><strong>Confidence:</strong> ${(station.confidence * 100).toFixed(1)}%</p>
              </div>
            `
          }
        };

        if (addMarkerCallback) {
          addMarkerCallback(markerInfo);
        }
      });
    }
  }

  // Global instance for easy access
  window.eVisionAICharging = new EVisionAIChargingAvailability();