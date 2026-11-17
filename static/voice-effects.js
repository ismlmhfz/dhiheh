/* The microphone is never played locally or uploaded outside the room call. */
window.PartyVoiceEffects=class {
    constructor(context,input,onFailure){this.context=context;this.input=input;this.onFailure=onFailure;this.closed=false}
    async select(effect){
        if(effect==='normal')return this.input;
        const context=this.context;
        if(!context?.audioWorklet||!window.AudioWorkletNode)throw Error('Voice effects are unavailable in this browser. Normal voice still works.');
        if(context.state!=='running'){
            await Promise.race([context.resume(),new Promise(resolve=>setTimeout(resolve,1200))]);
            if(context.state!=='running')throw Error('Tap Resume voice audio, then choose your effect again.');
        }
        if(!this.node){
            await context.audioWorklet.addModule('/static/voice-pitch-worklet.js?v=1');
            if(this.closed)throw Error('Voice disconnected.');
            this.node=new AudioWorkletNode(context,'party-voice',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1]});
            this.source=context.createMediaStreamSource(this.input);this.destination=context.createMediaStreamDestination();this.destination.channelCount=1;
            this.source.connect(this.node);this.node.connect(this.destination);
            this.node.onprocessorerror=()=>this.onFailure();
        }
        if(this.closed)throw Error('Voice disconnected.');
        this.node.port.postMessage(effect);
        return this.destination.stream;
    }
    close(){this.closed=true;this.source?.disconnect();this.node?.disconnect();if(this.node){this.node.onprocessorerror=null;this.node.port.close()}this.destination?.stream.getTracks().forEach(t=>t.stop())}
};
