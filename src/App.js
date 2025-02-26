import React, {Component, Fragment} from 'react';
import Plot from 'react-plotly.js';

// Used if system is on the cloud
class CustomWebSocket extends WebSocket {
  constructor(url, protocols, options) {
    // Disable SSL certificate verification
    options = {
      ...options,
      rejectUnauthorized: false,
    };
    super(url, protocols, options);
  }
}

export default class App extends Component {

  constructor(){
    super();
    
    // Declare state variables and functions to plot the orderbook and trade returns
    this.state = {response: null, orderbook: null, message: 'Waiting to Connect'};
    this.plotData = this.plotData.bind(this);
    this.plotBook = this.plotBook.bind(this);
  }

  // Connect to the websocket server to receive data from Python
  componentDidMount(){
    //const socket = new CustomWebSocket('wss://tradingalgoservery-78961753578.us-central1.run.app')
    const socket = new WebSocket('ws://0.0.0.0:8080')
    socket.onmessage = (evt) => {
      const resp = JSON.parse(evt.data)
      // Logging message such as trade output
      if(resp['type'] === 'log'){
        this.setState({ message: '> ' + resp['log']})
      }
      // Importing trade returns plot
      if(resp['type'] === 'plot'){
        this.setState({ response: resp['plot']})
      }
      // Importing orderbook plot
      if(resp['type'] === 'book'){
        this.setState({ orderbook: resp['book']})
      }
    }
  }

  // Plots the orderbook using Plotly.js
  plotBook(){
    const { orderbook } = this.state
    const hold = []
    if(orderbook !== null){
      hold.push(
        <Plot
          data={[{
            x: orderbook['bp'],
            y: orderbook['bv'],
            type: 'bar',
            marker: {
              color: 'red'
            }
          }]}
          layout={{
            title:{
              text: 'Bid OrderBook'
            },
            font: {
              color: 'white'
            },
            xaxis: {
              title: {
                  text: 'Bid Prices',
                  font: {
                      color: 'limegreen' // X-axis title font color
                  }
              },
              color: 'white'
            },
            yaxis: {
                title: {
                    text: 'Cumulative Bid Volume',
                    font: {
                        color: 'limegreen' // Y-axis title font color
                    }
                },
                color: 'white'
            },
            paper_bgcolor: 'black',
            plot_bgcolor: 'black'
          }}
        />
      )
      hold.push(
        <Plot
          data={[{
            x: orderbook['ap'],
            y: orderbook['av'],
            type: 'bar',
            marker: {
              color: 'cyan'
            }
          }]}
          layout={{
            title:{
              text: 'Ask OrderBook'
            },
            font: {
              color: 'white'
            },
            xaxis: {
              title: {
                  text: 'Ask Prices',
                  font: {
                      color: 'limegreen' // X-axis title font color
                  }
              },
              color: 'white'
            },
            yaxis: {
                title: {
                    text: 'Cumulative Ask Volume',
                    font: {
                        color: 'limegreen' // Y-axis title font color
                    }
                },
                color: 'white'
            },
            paper_bgcolor: 'black',
            plot_bgcolor: 'black'
          }}
        />
      )
    }
    return hold
  }

  // Plots the trade returns using React.js
  plotData(){
    const { response } = this.state;
    const hold = []
    if(response !== null){
      hold.push(
        <Plot
          data={[{
            x: response['x'],
            y: response['y'],
            type: 'scatter',
            mode: 'lines',
            marker: { color: 'limegreen' } 
          }]}
          layout={{
            title: {
              text: 'Trade Returns',
              font: {
                color: 'limegreen'
              }},
              xaxis: {
                title: {
                    text: 'Trade',
                    font: {
                        color: 'limegreen' // X-axis title font color
                    }
                },
                color: 'limegreen'
            },
            yaxis: {
                title: {
                    text: 'Returns',
                    font: {
                        color: 'limegreen' // Y-axis title font color
                    }
                },
                color: 'limegreen'
            },
            paper_bgcolor: 'black',
            plot_bgcolor: 'black'
          }}
        />
      )
    }
    return hold
  }

  render(){

    const mo = '> The Sharieff Bitcoin Algo Trader' // Title Bar Text

    return (
      <Fragment>
        <center>
          <div style={{backgroundColor: 'black', color: 'limegreen', fontSize: 35}}>{mo}</div>
          <br/>
          <br/>
          <div style={{color: 'limegreen', fontSize: 25}}>{this.state.message}</div>
          <br/>
          <div>{this.plotBook()}</div>
          <div>{this.plotData()}</div>
        </center>
      </Fragment>
    );
  }

}
