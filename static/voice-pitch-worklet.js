/* Two overlapping variable-delay grains shift pitch without slowing speech. */
class PartyVoiceProcessor extends AudioWorkletProcessor {
    constructor(){
        super();this.ring=new Float32Array(Math.ceil(sampleRate*.16));this.head=0;this.phase=0;this.filter=0;this.osc=0;
        this.effect='high';this.ratio=1.5;this.window=sampleRate*.055;this.minimum=sampleRate*.008;
        this.port.onmessage=({data})=>{this.effect=data;this.ratio={high:1.5,low:.75,scary:.65,robot:1}[data]||1;this.ring.fill(0);this.filter=0};
    }
    read(delay){
        const position=(this.head-delay+this.ring.length)%this.ring.length;
        const first=Math.floor(position),fraction=position-first;
        return this.ring[first]*(1-fraction)+this.ring[(first+1)%this.ring.length]*fraction;
    }
    process(inputs,outputs){
        const input=inputs[0]?.[0],output=outputs[0][0];
        for(let i=0;i<output.length;i++){
            const sample=input?.[i]||0;this.ring[this.head]=sample;
            const second=(this.phase+.5)%1,weight=.5-.5*Math.cos(2*Math.PI*this.phase);
            let shifted=this.read(this.minimum+this.phase*this.window)*weight+this.read(this.minimum+second*this.window)*(1-weight);
            if(this.effect==='robot')shifted=sample*(.35+.65*Math.sin(this.osc));
            if(this.effect==='scary'){
                this.filter+=(1-Math.exp(-2*Math.PI*1200/sampleRate))*(shifted-this.filter);
                shifted=Math.tanh(this.filter*1.6)*.7*(.88+.12*Math.sin(this.osc));
            }
            output[i]=Math.max(-.95,Math.min(.95,shifted*.9));
            this.phase=(this.phase+(1-this.ratio)/this.window+1)%1;
            this.osc=(this.osc+2*Math.PI*(this.effect==='robot'?45:7)/sampleRate)%(2*Math.PI);
            this.head=(this.head+1)%this.ring.length;
        }
        return true;
    }
}
registerProcessor('party-voice',PartyVoiceProcessor);
